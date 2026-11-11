"""Carga idempotente de OpinionesETL hacia OpinionesDW."""

from datetime import date

from sqlalchemy import insert, select, update

from application.services.sentiment import clasificar
from infrastructure.persistence import models as src
from infrastructure.persistence.warehouse import (
    WarehouseBase, DimClasificacion, DimCliente, DimFecha, DimFuente,
    DimProducto, DimTipoOpinion, FactOpinion,
)

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


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


def sincronizar_warehouse(origen_engine, dw_engine):
    """Clasifica opiniones sin etiqueta y carga dimensiones antes que hechos.

    La etiqueta original permanece en Opinion. Las predicciones quedan en
    AnalisisOpinion y se usan solamente donde falta la etiqueta original.
    """
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
    )
    with origen_engine.begin() as connection:
        opiniones = [dict(row) for row in connection.execute(consulta).mappings()]
        predicciones = []
        for opinion in opiniones:
            if opinion["IdClasificacion"] is None and opinion["Prediccion"] is None:
                prediccion = clasificar(opinion["Comentario"] or "")
                opinion["Prediccion"] = prediccion.id_clasificacion
                predicciones.append({"IdOpinion": opinion["IdOpinion"],
                                     "IdClasificacion": prediccion.id_clasificacion,
                                     "Confianza": prediccion.confianza,
                                     "ModeloVersion": prediccion.version})
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
