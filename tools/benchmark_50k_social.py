"""Prueba local de 50 000 comentarios sintéticos; revierte todos los cambios."""

from time import perf_counter
from uuid import uuid4

import pyodbc

from config.settings import settings


def main():
    from tools.create_sql_users import _connection_string

    connection = pyodbc.connect(_connection_string(settings.dw_name), timeout=30)
    total = 50_000
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.Stg_Opinion")
        stage_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*), MAX(IdOpinion) FROM dbo.Fact_Opinion")
        fact_before, max_id = cursor.fetchone()
        cursor.execute(
            "SELECT TOP (1) IdCliente,IdProducto,Fecha,IdFuente,Canal,"
            "IdClasificacion FROM dbo.Stg_Opinion WHERE IdTipoOpinion=3 "
            "ORDER BY IdOpinion"
        )
        sample = cursor.fetchone()
        if sample is None or max_id + total >= 2_147_483_647:
            raise RuntimeError("No hay muestra social o rango de IDs disponible")
        client, product, date, source, channel, classification = sample
        cursor.execute("BEGIN TRANSACTION")
        started = perf_counter()
        tvp_seconds = 0.0
        for group_start in range(0, total, 1000):
            batch_id = str(uuid4())
            tvp_started = perf_counter()
            for offset in range(group_start, group_start + 1000, 100):
                rows = ["TVP_OpinionSocial", "dbo"]
                for n in range(offset, offset + 100):
                    rows.append((
                        f"PERF50K_{n:05d}", max_id + 1 + n, client, product,
                        date, f"Comentario sintético de prueba {n}", source,
                        channel, 0, classification, 0, classification,
                    ))
                cursor.execute("EXEC dbo.usp_StagingSocial_TVP ?, ?", batch_id, rows)
            tvp_seconds += perf_counter() - tvp_started
            cursor.execute("SELECT COUNT(*) FROM dbo.Stg_Opinion WHERE IdEjecucion=?", batch_id)
            if cursor.fetchone()[0] != 1000:
                raise AssertionError("TVP no cargó el lote de 1000")
            for name in (
                "usp_CargarDimClasificacion", "usp_CargarDimTipoOpinion",
                "usp_CargarDimCliente", "usp_CargarDimProducto",
                "usp_CargarDimFuente", "usp_CargarDimFecha",
            ):
                cursor.execute(f"EXEC dbo.{name} ?", batch_id)
                cursor.fetchone()
            cursor.execute("EXEC dbo.usp_CargarFactOpinion ?", batch_id)
            first = tuple(cursor.fetchone())
            cursor.execute("EXEC dbo.usp_CargarFactOpinion ?", batch_id)
            second = tuple(cursor.fetchone())
            if first != (1000, 1000, 0, 0) or second != (1000, 0, 0, 1000):
                raise AssertionError(f"FACT inesperada: {first}, repetición: {second}")
        elapsed = perf_counter() - started
        connection.rollback()
        cursor.execute("SELECT COUNT(*) FROM dbo.Stg_Opinion")
        stage_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dbo.Fact_Opinion")
        fact_after = cursor.fetchone()[0]
        if (stage_before, fact_before) != (stage_after, fact_after):
            raise AssertionError("Los recuentos cambiaron tras ROLLBACK")
        print({"lotes": 50, "comentarios": total,
               "tvp_segundos": round(tvp_seconds, 3),
               "total_segundos": round(elapsed, 3),
               "fact_primera": first, "fact_repeticion": second,
               "staging_antes_despues": (stage_before, stage_after),
               "fact_antes_despues": (fact_before, fact_after)})
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
