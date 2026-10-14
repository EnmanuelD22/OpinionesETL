from pathlib import Path
import pandas as pd
from sqlalchemy import text
from application.services.DataTransformer import DataTransformer
from domain.entities.base import Base
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.database import engine
from infrastructure.services.sqlLoader import sqlLoader

DATA = Path(__file__).resolve().parent.parent.parent / "data"

class ETLPipeline:
    def __init__(self, nombre_proceso, extractor, transformer, loader):
        self.nombre_proceso = nombre_proceso
        self.extractor = extractor
        self.transformer = transformer
        self.loader = loader

    def ejecutar(self):
        print(f"\n{'=' * 50}\nEjecutando ETL: {self.nombre_proceso}\n{'=' * 50}")
        datos = self.extractor.extract()
        listos, rechazados_transformacion = self.transformer.transformar(datos)
        insertados, rechazados_carga = self.loader.cargar(listos)
        rechazados = rechazados_transformacion + rechazados_carga

        print(f"Procesados: {len(datos)} | Insertados: {insertados} | Rechazados: {rechazados}")
        return {
            "procesados": len(datos),
            "insertados": insertados,
            "rechazados": rechazados,
        }

def _crear_pipeline(nombre, archivo, tabla, requeridas, duplicados, **opciones):
    """Construye el pipeline estándar de lectura, transformación y carga."""
    return ETLPipeline(
        nombre,
        CsvExtractor(DATA / archivo),
        DataTransformer(requeridas, duplicados, **opciones),
        sqlLoader(tabla, duplicados), # Nota: asegúrate de que sqlLoader esté con minúscula inicial como en tu import
    )

def _ids_de(tabla, columna):
    consulta = text(f"SELECT [{columna}] FROM [{tabla}]")
    return set(pd.read_sql(consulta, con=engine)[columna])

def _preparar_catalogos():
    """Crea las tablas y agrega las clasificaciones y categorías faltantes."""
    Base.metadata.create_all(engine)

    existentes = set(pd.read_sql(
        text("SELECT IdClasificacion FROM Clasificacion"), con=engine
    )["IdClasificacion"])
    catalogo = pd.DataFrame([
        {"IdClasificacion": 1, "Tipo": "Positiva"}, # Cambiado a "Tipo" según tu base de datos
        {"IdClasificacion": 2, "Tipo": "Negativa"},
        {"IdClasificacion": 3, "Tipo": "Neutra"},
    ])
    faltantes = catalogo[~catalogo["IdClasificacion"].isin(existentes)]
    if not faltantes.empty:
        faltantes.to_sql("Clasificacion", con=engine, if_exists="append", index=False)

    productos = pd.read_csv(DATA / "products.csv", encoding="utf-8")
    columna_categoria = next(
        (col for col in ("Categoría", "CategorÃ­a") if col in productos.columns),
        None,
    )
    if columna_categoria is None:
        raise ValueError("products.csv debe incluir la columna Categoría")

    nombres = productos[columna_categoria].dropna().astype(str).str.strip().unique()
    categorias = pd.read_sql(text("SELECT Nombre FROM Categoria"), con=engine)["Nombre"]
    faltantes = sorted(set(nombres) - set(categorias))
    if faltantes:
        pd.DataFrame({"Nombre": faltantes}).to_sql(
            "Categoria", con=engine, if_exists="append", index=False
        )

def _mapa_categorias():
    categorias = pd.read_sql(
        text("SELECT IdCategoria, Nombre FROM Categoria"), con=engine
    )
    return dict(zip(categorias["Nombre"], categorias["IdCategoria"]))

def _pipelines_base():
   return [
        _crear_pipeline(
            "Fuentes de datos", "fuente_datos.csv", "Fuente_Datos",
            ["IdFuente", "TipoFuente", "FechaCarga"], ["IdFuente"],
        ),
        _crear_pipeline(
            "Clientes", "clients.csv", "Cliente", ["IdCliente", "Nombre", "email"],
            ["IdCliente"],
            renombrar={"Email": "email", "CORREO": "email", "correo": "email"},
        ),
    ]

def _pipeline_productos(mapa_categorias):
    return _crear_pipeline(
        "Productos", "products.csv", "Producto",
        ["IdProducto", "Nombre", "IdCategoria"], ["IdProducto"],
        renombrar={"Categoría": "IdCategoria", "CategorÃ­a": "IdCategoria"},
        mapas={"IdCategoria": mapa_categorias},
        columnas_salida=["IdProducto", "Nombre", "IdCategoria"],
    )

def _pipelines_opiniones(referencias):
    return [
        _crear_pipeline(
            "Opiniones de encuestas", "surveys_part1.csv", "Opinion",
            ["IdCliente", "IdProducto", "Fecha", "Comentario", "IdFuente",
             "IdClasificacion", "Puntaje"],
            ["IdCliente", "IdProducto", "Fecha", "Comentario"],
            renombrar={
                "Clasificación": "IdClasificacion",
                "ClasificaciÃƒÂ³n": "IdClasificacion",
                "PuntajeSatisfacciÃƒÂ³n": "Puntaje",
                "PuntajeSatisfacción": "Puntaje",
            },
            mapas={"IdClasificacion": {"Positiva": 1, "Negativa": 2, "Neutra": 3}},
            # Valores por defecto para rellenar las columnas requeridas
            valores_default={"IdFuente": 2, "Canal": "Encuestas", "IdOrigen": "CSV_SURVEY"}, 
            referencias=referencias,
            columnas_salida=["IdCliente", "IdProducto", "IdClasificacion", "IdFuente",
                             "Fecha", "Comentario", "Puntaje", "Canal", "IdOrigen"],
        ),
        _crear_pipeline(
            "Opiniones de redes sociales", "social_comments.csv", "Opinion",
            ["IdCliente", "IdProducto", "Fecha", "Comentario", "IdFuente"],
            ["IdCliente", "IdProducto", "Fecha", "Comentario"],
            # Valores por defecto para rellenar las columnas requeridas
            valores_default={"IdFuente": 5, "Canal": "Redes Sociales", "IdOrigen": "CSV_SOCIAL"}, 
            referencias=referencias,
            columnas_salida=["IdCliente", "IdProducto", "IdFuente", "Fecha", "Comentario", "Canal", "IdOrigen"],
        ),
        _crear_pipeline(
            "Opiniones de reseñas web", "web_reviews.csv", "Opinion",
            ["IdCliente", "IdProducto", "Fecha", "Comentario", "IdFuente",
             "Puntaje"],
            ["IdCliente", "IdProducto", "Fecha", "Comentario"],
            renombrar={"Rating": "Puntaje"},
            # Valores por defecto para rellenar las columnas requeridas
            valores_default={"IdFuente": 1, "Canal": "Reseñas Web", "IdOrigen": "CSV_WEB"}, 
            referencias=referencias,
            columnas_salida=["IdCliente", "IdProducto", "IdFuente", "Fecha",
                             "Comentario", "Puntaje", "Canal", "IdOrigen"],
        ),
    ]

def ejecutar_etl():
    """Prepara catálogos y ejecuta pipelines en orden de dependencias."""
    _preparar_catalogos()
    resumen = {"procesados": 0, "insertados": 0, "rechazados": 0}

    def ejecutar(pipeline):
        resultados = pipeline.ejecutar()
        for metrica in resumen:
            resumen[metrica] += resultados[metrica]

    for pipeline in _pipelines_base():
        ejecutar(pipeline)

    ejecutar(_pipeline_productos(_mapa_categorias()))

    referencias = {
        "IdCliente": _ids_de("Cliente", "IdCliente"),
        "IdProducto": _ids_de("Producto", "IdProducto"),
        "IdFuente": _ids_de("Fuente_Datos", "IdFuente"), # Corregido: Fuente_Datos
        "IdClasificacion": _ids_de("Clasificacion", "IdClasificacion"),
    }
    for pipeline in _pipelines_opiniones(referencias):
        ejecutar(pipeline)

    print("\nResumen del proceso ETL")
    print(
        f"Procesados: {resumen['procesados']} | "
        f"Insertados: {resumen['insertados']} | "
        f"Rechazados: {resumen['rechazados']}"
    )