"""Carga staging con BULK/fast_executemany, TVP e INSERT … SELECT."""

import csv
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

import pyodbc

from application.exceptions.etl_exceptions import PersistenceError


STAGE_COLUMNS = (
    "IdOrigen", "IdOpinion", "IdCliente", "IdProducto", "Fecha",
    "Comentario", "IdFuente", "Canal", "Puntaje",
    "IdClasificacionOriginal", "IdClasificacionPredicha", "IdClasificacion",
)
SURVEY_BATCH_SIZE = 500
SOCIAL_TVP_BATCH_SIZE = 100
REJECTION_BATCH_SIZE = 500


class SetBasedStagingWriter:
    def __init__(self, dw_engine, bulk_dir: Path):
        self.dw_engine = dw_engine
        self.bulk_dir = Path(bulk_dir)

    @staticmethod
    def _chunks(rows, size):
        for start in range(0, len(rows), size):
            yield rows[start:start + size]

    @staticmethod
    def _stage_values(row):
        return tuple(row[column] for column in STAGE_COLUMNS)

    def _survey_csv(self, rows):
        self.bulk_dir.mkdir(parents=True, exist_ok=True)
        path = self.bulk_dir / f"encuestas_preparadas_{uuid4().hex}.csv"
        try:
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(STAGE_COLUMNS)
                for row in rows:
                    writer.writerow(["" if row[column] is None else row[column]
                                     for column in STAGE_COLUMNS])
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path

    @staticmethod
    def _bulk_file_unavailable(error: pyodbc.Error) -> bool:
        """Solo los errores de apertura/lectura del archivo habilitan fallback."""
        message = " ".join(str(part) for part in error.args)
        return any(f"({code})" in message for code in (4860, 4861, 4862))

    @staticmethod
    def _clear_batch(cursor, batch_id):
        cursor.execute("DELETE FROM dbo.Stg_Opinion WHERE IdEjecucion = ?", batch_id)
        cursor.execute("DELETE FROM dbo.Stg_Rechazo WHERE IdEjecucion = ?", batch_id)

    @staticmethod
    def _insert_surveys_batch(cursor, batch_id, rows):
        statement = (
            "INSERT INTO dbo.Stg_Opinion (IdEjecucion, IdTipoOpinion, "
            + ", ".join(STAGE_COLUMNS) + ") VALUES (?, 1, "
            + ", ".join("?" for _ in STAGE_COLUMNS) + ")"
        )
        cursor.fast_executemany = True
        for chunk in SetBasedStagingWriter._chunks(rows, SURVEY_BATCH_SIZE):
            cursor.executemany(statement, [(batch_id, *SetBasedStagingWriter._stage_values(row))
                                           for row in chunk])

    @staticmethod
    def _insert_social_tvp(cursor, batch_id, rows):
        for chunk in SetBasedStagingWriter._chunks(rows, SOCIAL_TVP_BATCH_SIZE):
            # pyodbc 5.x no infiere el tipo de un NULL en la primera fila TVP.
            # 0 queda fuera del dominio válido y el procedimiento lo convierte a NULL.
            def transport_row(row):
                values = list(SetBasedStagingWriter._stage_values(row))
                for index in (8, 9, 10):
                    if values[index] is None:
                        values[index] = 0
                return tuple(values)

            tvp = ["TVP_OpinionSocial", "dbo",
                   *(transport_row(row) for row in chunk)]
            cursor.execute("EXEC dbo.usp_StagingSocial_TVP ?, ?", batch_id, tvp)

    @staticmethod
    def _insert_rejections(cursor, batch_id, rows):
        statement = (
            "INSERT INTO dbo.Stg_Rechazo (IdEjecucion, Origen, IdOrigen, Motivo) "
            "VALUES (?, ?, ?, ?)"
        )
        cursor.fast_executemany = True
        for chunk in SetBasedStagingWriter._chunks(rows, REJECTION_BATCH_SIZE):
            cursor.executemany(statement, [
                (batch_id, row["Origen"], row["IdOrigen"], row["Motivo"])
                for row in chunk
            ])

    def write_set_based(self, batch_id: str, surveys: list[dict], social: list[dict],
                        rejections: list[dict], survey_mode: str = "auto") -> dict:
        if survey_mode not in {"auto", "bulk", "batch"}:
            raise ValueError("survey_mode debe ser auto, bulk o batch")
        UUID(batch_id)
        csv_path = None
        connection = None
        started = perf_counter()
        try:
            if surveys and survey_mode != "batch":
                csv_path = self._survey_csv(surveys)
            connection = self.dw_engine.raw_connection()
            cursor = connection.cursor()
            self._clear_batch(cursor, batch_id)

            survey_started = perf_counter()
            fallback = None
            if csv_path is not None:
                try:
                    cursor.execute("EXEC dbo.usp_CargarEncuestasBulkStaging ?, ?",
                                   batch_id, str(csv_path))
                    inserted = cursor.fetchone()[0]
                    if inserted != len(surveys):
                        raise PersistenceError(
                            "BULK INSERT no cargó todas las encuestas validadas"
                        )
                    selected_survey_mode = "bulk"
                except pyodbc.Error as error:
                    if survey_mode != "auto" or not self._bulk_file_unavailable(error):
                        raise
                    # El procedimiento hace ROLLBACK de toda la transacción.
                    # Abrimos una transacción nueva y repetimos la limpieza.
                    connection.rollback()
                    cursor = connection.cursor()
                    self._clear_batch(cursor, batch_id)
                    self._insert_surveys_batch(cursor, batch_id, surveys)
                    selected_survey_mode = "batch"
                    fallback = "archivo_inaccesible"
            else:
                if surveys:
                    self._insert_surveys_batch(cursor, batch_id, surveys)
                selected_survey_mode = "batch"
            survey_seconds = perf_counter() - survey_started

            social_started = perf_counter()
            if social:
                self._insert_social_tvp(cursor, batch_id, social)
            social_seconds = perf_counter() - social_started

            review_started = perf_counter()
            cursor.execute("EXEC dbo.usp_PrepararResenasRelacionales ?", batch_id)
            review_counts = cursor.fetchone()
            review_seconds = perf_counter() - review_started
            if review_counts is None:
                raise PersistenceError("El procedimiento de reseñas no devolvió conteos")

            if rejections:
                self._insert_rejections(cursor, batch_id, rejections)
            connection.commit()
            return {
                "resena": {"leidos": review_counts[0],
                           "preparados": review_counts[1],
                           "rechazados": review_counts[2]},
                "encuesta_modo": selected_survey_mode,
                "encuesta_fallback": fallback,
                "segundos": {"encuesta": round(survey_seconds, 4),
                             "social": round(social_seconds, 4),
                             "resena": round(review_seconds, 4),
                             "total": round(perf_counter() - started, 4)},
                "lote_tvp": SOCIAL_TVP_BATCH_SIZE,
            }
        except (pyodbc.Error, OSError, ValueError) as error:
            if connection is not None:
                connection.rollback()
            raise PersistenceError("No fue posible cargar staging por conjuntos") from error
        except Exception:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()
            if csv_path is not None:
                csv_path.unlink(missing_ok=True)
