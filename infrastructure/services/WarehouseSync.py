"""Carga idempotente de OpinionesETL hacia OpinionesDW."""

from datetime import date
from math import isfinite

from sqlalchemy import insert, select, update

from application.interfaces.services.ISentimentClassifier import ISentimentClassifier
from application.services.lexicon_classifier import LexiconClassifier
from application.services.sentiment import Prediccion
from infrastructure.persistence import models as src
from infrastructure.persistence.warehouse import (
    WarehouseBase, DimClasificacion, DimCliente, DimFecha, DimFuente,
    DimProducto, DimTipoOpinion, FactOpinion,
)

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")
NLP_BATCH_SIZE = 16


def _sincronizar(connection, model, filas):
    """Inserta faltantes y actualiza atributos modificados por clave primaria."""
    tabla = model.__table__
    pk = list(tabla.primary_key.columns)[0].name
    existentes = {
        row[pk]: dict(row)
        for row in connection.execute(select(tabla)).mappings()
    }
    nuevos = []
    for clave, fila in filas.items():
        anterior = existentes.get(clave)
        if anterior is None:
            nuevos.append(fila)
        elif any(anterior[c] != valor for c, valor in fila.items()):
            connection.execute(update(tabla).where(tabla.c[pk] == clave).values(**fila))
    if nuevos:
        connection.execute(insert(tabla), nuevos)
    return len(nuevos)


def _predecir_pendientes(opiniones, classifier: ISentimentClassifier):
    """Valida el lote completo antes de permitir escrituras de predicciones."""
    pendientes = [op for op in opiniones
                  if op["IdClasificacion"] is None and op["Prediccion"] is None]
    if not pendientes:
        return []
    comentarios = [op["Comentario"] for op in pendientes]
    if any(not isinstance(texto, str) or not texto.strip() for texto in comentarios):
        raise ValueError("No se puede clasificar una opinión sin comentario válido")
    predicciones = classifier.predict_batch(comentarios, batch_size=NLP_BATCH_SIZE)
    if not isinstance(predicciones, list) or len(predicciones) != len(pendientes):
        raise ValueError("El clasificador debe devolver una predicción por opinión")
    registros = []
    for opinion, prediccion in zip(pendientes, predicciones):
        if not isinstance(prediccion, Prediccion):
            raise ValueError("El clasificador devolvió un resultado inválido")
        clase = prediccion.id_clasificacion
        confianza = prediccion.confianza
        version = prediccion.version
        if type(clase) is not int or clase not in (1, 2, 3):
            raise ValueError("El clasificador devolvió una clase inválida")
        if (isinstance(confianza, bool) or not isinstance(confianza, (int, float))
                or not isfinite(confianza) or not 0 <= confianza <= 1):
            raise ValueError("El clasificador devolvió una confianza inválida")
        if not isinstance(version, str) or not version.strip() or len(version) > 50:
            raise ValueError("El clasificador devolvió una versión inválida")
        registros.append({"IdOpinion": opinion["IdOpinion"],
                          "IdClasificacion": clase, "Confianza": confianza,
                          "ModeloVersion": version})
    for opinion, registro in zip(pendientes, registros):
        opinion["Prediccion"] = registro["IdClasificacion"]
    return registros


def sincronizar_warehouse(origen_engine, dw_engine,
                          classifier: ISentimentClassifier | None = None):
    """Clasifica opiniones sin etiqueta y carga dimensiones antes que hechos.

    La etiqueta original permanece en Opinion. Las predicciones quedan en
    AnalisisOpinion y se usan solamente donde falta la etiqueta original.
    """
    if classifier is None:
        classifier = LexiconClassifier()
    src.Base.metadata.create_all(origen_engine)
    WarehouseBase.metadata.create_all(dw_engine)
    o, c, p, cat = src.OpinionModel, src.ClienteModel, src.ProductoModel, src.CategoriaModel
    f, t, a = src.FuenteDatosModel, src.TipoOpinionModel, src.AnalisisOpinionModel
    consulta = (
        select(o.IdOpinion, o.Fecha, o.Comentario, o.Puntaje, o.Canal,
               o.IdCliente, c.Nombre.label("Cliente"), c.email,
               o.IdProducto, p.Nombre.label("Producto"), cat.Nombre.label("Categoria"),
               o.IdFuente, f.TipoFuente, o.IdTipoOpinion, t.Nombre.label("TipoOpinion"),
               o.IdClasificacion, a.IdClasificacion.label("Prediccion"))
        .outerjoin(c, o.IdCliente == c.IdCliente)
        .outerjoin(p, o.IdProducto == p.IdProducto)
        .outerjoin(cat, p.IdCategoria == cat.IdCategoria)
        .outerjoin(f, o.IdFuente == f.IdFuente)
        .outerjoin(t, o.IdTipoOpinion == t.IdTipoOpinion)
        .outerjoin(a, o.IdOpinion == a.IdOpinion)
        .order_by(o.IdOpinion)
    )
    with origen_engine.begin() as connection:
        opiniones = [dict(row) for row in connection.execute(consulta).mappings()]
        predicciones = _predecir_pendientes(opiniones, classifier)
        if predicciones:
            connection.execute(insert(a), predicciones)

    dimensiones = {model: {} for model in (
        DimClasificacion, DimCliente, DimFecha, DimFuente, DimProducto, DimTipoOpinion
    )}
    hechos = {}
    clasificaciones = {1: "Positiva", 2: "Negativa", 3: "Neutra"}
    for op in opiniones:
        required = ("Fecha", "IdCliente", "Cliente", "IdProducto", "Producto", "Categoria",
                    "IdFuente", "TipoFuente", "Canal", "IdTipoOpinion", "TipoOpinion")
        if any(op[key] is None for key in required):
            raise ValueError(f"Opinion {op['IdOpinion']} tiene referencias incompletas")
        fecha = op["Fecha"]
        if not isinstance(fecha, date):
            raise ValueError(f"Fecha inválida en Opinion {op['IdOpinion']}")
        clase = op["IdClasificacion"] or op["Prediccion"]
        if clase not in clasificaciones:
            raise ValueError(f"Clasificación inválida en Opinion {op['IdOpinion']}")
        id_fecha = int(fecha.strftime("%Y%m%d"))
        elementos = {
            DimClasificacion: (clase, {"IdClasificacion": clase, "Tipo": clasificaciones[clase]}),
            DimCliente: (op["IdCliente"], {"IdCliente": op["IdCliente"], "Nombre": op["Cliente"], "Email": op["email"]}),
            DimFecha: (id_fecha, {"IdFecha": id_fecha, "Fecha": fecha, "Anio": fecha.year,
                                      "Trimestre": (fecha.month - 1) // 3 + 1, "Mes": fecha.month,
                                      "NombreMes": MESES[fecha.month - 1],
                                      "AnioMes": fecha.strftime("%Y-%m"), "Dia": fecha.day}),
            DimFuente: (op["IdFuente"], {"IdFuente": op["IdFuente"], "Canal": op["Canal"],
                                            "TipoFuente": op["TipoFuente"]}),
            DimProducto: (op["IdProducto"], {"IdProducto": op["IdProducto"],
                                                "Nombre": op["Producto"], "Categoria": op["Categoria"]}),
            DimTipoOpinion: (op["IdTipoOpinion"], {"IdTipoOpinion": op["IdTipoOpinion"],
                                                     "Nombre": op["TipoOpinion"]}),
        }
        for model, (key, values) in elementos.items():
            previous = dimensiones[model].get(key)
            if previous is not None and previous != values:
                raise ValueError(f"Dimensión {model.__tablename__} ambigua para clave {key}")
            dimensiones[model][key] = values
        hechos[op["IdOpinion"]] = {
            "IdOpinion": op["IdOpinion"], "IdFecha": id_fecha,
            "IdCliente": op["IdCliente"], "IdProducto": op["IdProducto"],
            "IdFuente": op["IdFuente"], "IdClasificacion": clase,
            "Puntaje": op["Puntaje"], "Comentario": op["Comentario"],
            "IdTipoOpinion": op["IdTipoOpinion"],
        }
    with dw_engine.begin() as connection:
        for model, filas in dimensiones.items():
            _sincronizar(connection, model, filas)
        insertados = _sincronizar(connection, FactOpinion, hechos)
    return {"opiniones_origen": len(opiniones), "hechos_insertados": insertados,
            "hechos_totales": len(hechos), "predicciones_nuevas": len(predicciones)}
