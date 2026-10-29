"""Construcción de pipelines sin conocer adaptadores concretos.

Las reglas de negocio del flujo viven aquí, mientras que las fábricas de
extracción y carga llegan por inyección desde el punto de composición.
"""

#region Imports
from pathlib import Path
from typing import Callable, Mapping

from application.interfaces.services.ICatalogService import ICatalogService
from application.interfaces.services.IExtractor import IExtractor
from application.interfaces.services.ILoader import ILoader
from application.models.schema import DataSchema, FieldRule
from application.services.DataTransformer import DataTransformer
from application.services.etl_pipeline import ETLApplication, ETLPipeline
#endregion


#region Types
ExtractorFactory = Callable[[Path], IExtractor]
LoaderFactory = Callable[[str, list[str]], ILoader]
#endregion


#region Catalog identifiers

TIPO_OPINION_ENCUESTA = 1
TIPO_OPINION_RESENA = 2
TIPO_OPINION_COMENTARIO_SOCIAL = 3



#region Schemas
FUENTES_SCHEMA = DataSchema.from_rules([
    FieldRule("IdFuente", "integer"),
    FieldRule("TipoFuente", "text", max_length=50),
    FieldRule("FechaCarga", "date"),
])

CLIENTES_SCHEMA = DataSchema.from_rules([
    FieldRule("IdCliente", "integer"),
    FieldRule("Nombre", "text", max_length=100),
    FieldRule("email", "text", max_length=100),
])

PRODUCTOS_SCHEMA = DataSchema.from_rules([
    FieldRule("IdProducto", "integer"),
    FieldRule("Nombre", "text", max_length=100),
    FieldRule("IdCategoria", "integer"),
])

OPINIONES_SCHEMA = DataSchema.from_rules([
    FieldRule("IdCliente", "integer"),
    FieldRule("IdProducto", "integer"),
    FieldRule("Fecha", "date"),
    FieldRule("Comentario", "text"),
    FieldRule("IdFuente", "integer"),
    FieldRule("IdClasificacion", "integer", required=False),
    FieldRule("IdTipoOpinion", "integer", required=False),
    FieldRule("Puntaje", "number", required=False, minimum=1, maximum=5),
    FieldRule("Canal", "text", required=False, max_length=50),
    FieldRule("IdOrigen", "text", required=False, max_length=50),
])
#endregion


#region Pipeline builders
def _crear_pipeline(
    nombre: str,
    archivo: str,
    tabla: str,
    requeridas: list[str],
    duplicados: list[str],
    data_dir: Path,
    extractor_factory: ExtractorFactory,
    loader_factory: LoaderFactory,
    **opciones,
) -> ETLPipeline:
    """Construye un pipeline con sus puertos ya conectados."""

    return ETLPipeline(
        nombre_proceso=nombre,
        extractor=extractor_factory(data_dir / archivo),
        transformer=DataTransformer(requeridas, duplicados, **opciones),
        loader=loader_factory(tabla, duplicados),
    )


def _pipelines_base(
    data_dir: Path,
    extractor_factory: ExtractorFactory,
    loader_factory: LoaderFactory,
) -> list[ETLPipeline]:
    """Define las cargas maestras que no dependen de otras cargas."""

    return [
        _crear_pipeline(
            "Fuentes de datos", "fuente_datos.csv", "Fuente_Datos",
            ["IdFuente", "TipoFuente", "FechaCarga"], ["IdFuente"],
            data_dir, extractor_factory, loader_factory,
            esquema=FUENTES_SCHEMA,
        ),
        _crear_pipeline(
            "Clientes", "clients.csv", "Cliente",
            ["IdCliente", "Nombre", "email"], ["IdCliente"],
            data_dir, extractor_factory, loader_factory,
            renombrar={"Email": "email", "CORREO": "email", "correo": "email"},
            esquema=CLIENTES_SCHEMA,
        ),
    ]


def _pipeline_productos(
    mapa_categorias: Mapping[str, int],
    data_dir: Path,
    extractor_factory: ExtractorFactory,
    loader_factory: LoaderFactory,
) -> ETLPipeline:
    """Construye el pipeline de productos después de preparar categorías."""

    return _crear_pipeline(
        "Productos", "products.csv", "Producto",
        ["IdProducto", "Nombre", "IdCategoria"], ["IdProducto"],
        data_dir, extractor_factory, loader_factory,
        renombrar={
            "Categoría": "IdCategoria",
            "CategorÃ­a": "IdCategoria",
            "CategorÃƒÂ­a": "IdCategoria",
        },
        mapas={"IdCategoria": dict(mapa_categorias)},
        columnas_salida=["IdProducto", "Nombre", "IdCategoria"],
        esquema=PRODUCTOS_SCHEMA,
    )


def _pipelines_opiniones(
    referencias: Mapping[str, set[int]],
    data_dir: Path,
    extractor_factory: ExtractorFactory,
    loader_factory: LoaderFactory,
) -> list[ETLPipeline]:
    """Construye las cargas de opiniones con referencias ya existentes."""

    return [
        _crear_pipeline(
            "Opiniones de encuestas", "surveys_part1.csv", "Opinion",
            ["IdCliente", "IdProducto", "Fecha", "Comentario", "IdFuente",
             "IdClasificacion", "Puntaje"],
            ["IdCliente", "IdProducto", "Fecha", "Comentario"],
            data_dir, extractor_factory, loader_factory,
            renombrar={
                "Clasificación": "IdClasificacion",
                "ClasificaciÃ³n": "IdClasificacion",
                "ClasificaciÃƒÆ’Ã‚Â³n": "IdClasificacion",
                "PuntajeSatisfacción": "Puntaje",
                "PuntajeSatisfacciÃ³n": "Puntaje",
                "PuntajeSatisfacciÃƒÆ’Ã‚Â³n": "Puntaje",
            },
            mapas={"IdClasificacion": {"Positiva": 1, "Negativa": 2, "Neutra": 3}},
            valores_default={
                "IdFuente": 2,
                "Canal": "Encuestas",
                "IdOrigen": "CSV_SURVEY",
                "IdTipoOpinion": TIPO_OPINION_ENCUESTA,
            },
            referencias=referencias,
            columnas_salida=[
                "IdCliente", "IdProducto", "IdClasificacion", "IdFuente",
                "IdTipoOpinion", "Fecha", "Comentario", "Puntaje", "Canal", "IdOrigen",
            ],
            esquema=OPINIONES_SCHEMA,
        ),
        _crear_pipeline(
            "Opiniones de redes sociales", "social_comments.csv", "Opinion",
            ["IdCliente", "IdProducto", "Fecha", "Comentario", "IdFuente"],
            ["IdCliente", "IdProducto", "Fecha", "Comentario"],
            data_dir, extractor_factory, loader_factory,
            valores_default={
                "IdFuente": 5,
                "Canal": "Redes Sociales",
                "IdOrigen": "CSV_SOCIAL",
                "IdTipoOpinion": TIPO_OPINION_COMENTARIO_SOCIAL,
            },
            referencias=referencias,
            columnas_salida=[
                "IdCliente", "IdProducto", "IdFuente", "IdTipoOpinion", "Fecha",
                "Comentario", "Canal", "IdOrigen",
            ],
            esquema=OPINIONES_SCHEMA,
        ),
        _crear_pipeline(
            "Opiniones de reseñas web", "web_reviews.csv", "Opinion",
            ["IdCliente", "IdProducto", "Fecha", "Comentario", "IdFuente", "Puntaje"],
            ["IdCliente", "IdProducto", "Fecha", "Comentario"],
            data_dir, extractor_factory, loader_factory,
            renombrar={"Rating": "Puntaje"},
            valores_default={
                "IdFuente": 1,
                "Canal": "Reseñas Web",
                "IdOrigen": "CSV_WEB",
                "IdTipoOpinion": TIPO_OPINION_RESENA,
            },
            referencias=referencias,
            columnas_salida=[
                "IdCliente", "IdProducto", "IdFuente", "IdTipoOpinion", "Fecha",
                "Comentario", "Puntaje", "Canal", "IdOrigen",
            ],
            esquema=OPINIONES_SCHEMA,
        ),
    ]
#endregion


#region Application factory
def build_etl_application(
    data_dir: Path,
    catalog_service: ICatalogService,
    extractor_factory: ExtractorFactory,
    loader_factory: LoaderFactory,
) -> ETLApplication:
    """Construye el caso de uso con todas sus dependencias abstractas."""

    return ETLApplication(
        catalog_service=catalog_service,
        pipelines_base=_pipelines_base(data_dir, extractor_factory, loader_factory),
        pipeline_product_factory=lambda categorias: _pipeline_productos(
            categorias, data_dir, extractor_factory, loader_factory
        ),
        pipelines_opiniones_factory=lambda referencias: _pipelines_opiniones(
            referencias, data_dir, extractor_factory, loader_factory
        ),
    )
#endregion