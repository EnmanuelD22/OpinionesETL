"""Orquesta los procedimientos de dimensiones y hechos para un lote preparado."""

from time import perf_counter
from uuid import UUID

from application.exceptions.etl_exceptions import PersistenceError


PROCEDURES = (
    ("clasificacion", "usp_CargarDimClasificacion"),
    ("tipo_opinion", "usp_CargarDimTipoOpinion"),
    ("cliente", "usp_CargarDimCliente"),
    ("producto", "usp_CargarDimProducto"),
    ("fuente", "usp_CargarDimFuente"),
    ("fecha", "usp_CargarDimFecha"),
    ("fact_opinion", "usp_CargarFactOpinion"),
)


class AnalyticWarehouseLoader:
    def __init__(self, dw_engine):
        self.dw_engine = dw_engine

    def load(self, batch_id: str) -> dict:
        UUID(batch_id)
        connection = self.dw_engine.raw_connection()
        results = {}
        started = perf_counter()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*), COUNT(DISTINCT IdOpinion) "
                "FROM dbo.Stg_Opinion WHERE IdEjecucion = ?", batch_id
            )
            count, distinct_count = cursor.fetchone()
            if not count or count != distinct_count:
                raise PersistenceError("Lote vacío o con IdOpinion duplicado en staging")
            for label, procedure in PROCEDURES:
                cursor.execute(f"EXEC dbo.{procedure} @IdEjecucion = ?", batch_id)
                row = cursor.fetchone()
                if row is None:
                    raise PersistenceError(f"{procedure} no devolvió métricas")
                columns = [column[0] for column in cursor.description]
                results[label] = dict(zip(columns, row))
            # Las transacciones internas de SQL Server quedan anidadas en la
            # transacción de esta conexión; confirmar el lote completo junto.
            connection.commit()
            return {"id_ejecucion": batch_id, "staging": count,
                    "procedimientos": results,
                    "segundos": round(perf_counter() - started, 4)}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
