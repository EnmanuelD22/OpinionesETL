"""Punto de composición de los adaptadores concretos."""

#region Imports
from pathlib import Path
import os

from sqlalchemy import create_engine

from config.settings import settings

from application.interfaces.services.ISentimentClassifier import ISentimentClassifier
from application.services.pipeline_factory import build_etl_application
from application.services.lexicon_classifier import LexiconClassifier
from infrastructure.database import get_engine
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.services.SqlCatalogService import SqlCatalogService
from infrastructure.services.SqlTableExtractor import SqlTableExtractor
from infrastructure.services.sqlLoader import SqlLoader
#endregion


#region Composition root
DATA = Path(__file__).resolve().parent.parent / "data"


def create_loader(table: str, duplicate_keys: list[str]) -> SqlLoader:
    """Construye el adaptador SQL con el motor compartido."""

    return SqlLoader(table, duplicate_keys, db_engine=get_engine())


def create_sentiment_classifier() -> ISentimentClassifier:
    """Selecciona la línea base aprobada para el ETL activo."""
    return LexiconClassifier()


def create_application():
    """Construye la aplicación y conecta todos sus adaptadores."""

    engine = get_engine()
    web_database = os.getenv("WEB_SOURCE_DB_NAME")
    web_engine = (create_engine(settings.connection_string_for(web_database))
                  if web_database else None)

    def extractor(path: Path):
        if path.name == "web_reviews.csv" and web_engine is not None:
            return SqlTableExtractor(web_engine, os.getenv("WEB_SOURCE_TABLE", "WebReviews"))
        return CsvExtractor(path)

    return build_etl_application(
        data_dir=DATA,
        catalog_service=SqlCatalogService(
            db_engine=engine,
            products_extractor=CsvExtractor(DATA / "products.csv"),
        ),
        extractor_factory=extractor,
        loader_factory=create_loader,
    )
#endregion
