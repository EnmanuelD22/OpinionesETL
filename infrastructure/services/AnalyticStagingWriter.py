"""Escribe por lotes en staging sin tocar las tablas de dimensiones ni hechos."""

from uuid import UUID

from sqlalchemy import MetaData, Table, delete, insert
from sqlalchemy.exc import SQLAlchemyError

from application.exceptions.etl_exceptions import PersistenceError


class AnalyticStagingWriter:
    def __init__(self, dw_engine):
        self.dw_engine = dw_engine

    def write(self, batch_id: str, opinions: list[dict], rejections: list[dict]) -> None:
        try:
            UUID(batch_id)
            schema = "dbo" if self.dw_engine.dialect.name == "mssql" else None
            metadata = MetaData()
            opinions_table = Table("Stg_Opinion", metadata, schema=schema,
                                   autoload_with=self.dw_engine)
            rejections_table = Table("Stg_Rechazo", metadata, schema=schema,
                                     autoload_with=self.dw_engine)
            if self.dw_engine.dialect.name == "mssql":
                batch_value = UUID(batch_id)
                opinions = [{**row, "IdEjecucion": batch_value} for row in opinions]
                rejections = [{**row, "IdEjecucion": batch_value} for row in rejections]
            else:
                batch_value = batch_id
            with self.dw_engine.begin() as connection:
                connection.execute(delete(opinions_table).where(
                    opinions_table.c.IdEjecucion == batch_value))
                connection.execute(delete(rejections_table).where(
                    rejections_table.c.IdEjecucion == batch_value))
                if opinions:
                    connection.execute(insert(opinions_table), opinions)
                if rejections:
                    connection.execute(insert(rejections_table), rejections)
        except (SQLAlchemyError, ValueError) as error:
            raise PersistenceError(f"No fue posible escribir staging: {error}") from error
