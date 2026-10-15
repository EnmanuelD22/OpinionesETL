"""Punto de composición de los adaptadores concretos."""

#region Imports
from pathlib import Path

from application.services.pipeline_factory import build_etl_application
from infrastructure.database import get_engine
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.services.SqlCatalogService import SqlCatalogService
from infrastructure.services.sqlLoader import SqlLoader
#endregion


#region Composition root
DATA = Path(__file__).resolve().parent.parent / "data"


def create_loader(table: str, duplicate_keys: list[str]) -> SqlLoader:
    """Construye el adaptador SQL con el motor compartido."""

    return SqlLoader(table, duplicate_keys, db_engine=get_engine())


def create_application():
    """Construye la aplicación y conecta todos sus adaptadores."""

    engine = get_engine()
    return build_etl_application(
        data_dir=DATA,
        catalog_service=SqlCatalogService(
            db_engine=engine,
            products_extractor=CsvExtractor(DATA / "products.csv"),
        ),
        extractor_factory=CsvExtractor,
        loader_factory=create_loader,
    )
#endregion
