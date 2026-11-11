"""Extractor de reseñas desde una tabla relacional de origen."""

import pandas as pd
from sqlalchemy import MetaData, Table, select
from sqlalchemy.exc import SQLAlchemyError

from application.exceptions.etl_exceptions import ExtractionError
from application.interfaces.services.IExtractor import IExtractor


class SqlTableExtractor(IExtractor):
    def __init__(self, db_engine, table_name: str):
        self.db_engine = db_engine
        self.table_name = table_name

    def extract(self) -> pd.DataFrame:
        try:
            table = Table(self.table_name, MetaData(), autoload_with=self.db_engine)
            return pd.read_sql(select(table), con=self.db_engine)
        except (SQLAlchemyError, ValueError, KeyError) as error:
            raise ExtractionError(f"No fue posible leer {self.table_name}: {error}") from error
