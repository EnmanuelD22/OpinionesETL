"""Prueba de integración local del origen relacional al esquema dimensional."""

import unittest
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, func, select, update

from application.services.sentiment import clasificar
from application.services.pipeline_factory import build_etl_application
from infrastructure.services.WarehouseSync import sincronizar_warehouse
from dashboard import obtener_kpis
from infrastructure.persistence.models import AnalisisOpinionModel, OpinionModel
from infrastructure.persistence.warehouse import FactOpinion
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.services.SqlCatalogService import SqlCatalogService
from infrastructure.services.SqlTableExtractor import SqlTableExtractor
from infrastructure.services.sqlLoader import SqlLoader


class WarehouseTests(unittest.TestCase):
    def test_sentiment_baseline_and_sql_extractor(self):
        self.assertEqual(clasificar("Muy mala calidad").id_clasificacion, 2)
        self.assertEqual(clasificar("No lo recomiendo").id_clasificacion, 2)
        self.assertEqual(clasificar("Funciona perfecto").id_clasificacion, 1)
        self.assertEqual(clasificar("Sin comentarios adicionales").id_clasificacion, 3)
        db = create_engine("sqlite:///:memory:")
        self.addCleanup(db.dispose)
        pd.DataFrame([{"IdReview": "W1", "Comentario": "Funciona perfecto"}]).to_sql(
            "WebReviews", db, index=False
        )
        self.assertEqual(SqlTableExtractor(db, "WebReviews").extract().iloc[0]["IdReview"], "W1")

    def test_relational_to_warehouse_is_repeatable_and_preserves_source_label(self):
        data = Path(__file__).resolve().parents[1] / "data"
        source = create_engine("sqlite:///:memory:")
        warehouse = create_engine("sqlite:///:memory:")
        self.addCleanup(source.dispose)
        self.addCleanup(warehouse.dispose)
        app = build_etl_application(
            data, SqlCatalogService(source, CsvExtractor(data / "products.csv")),
            CsvExtractor, lambda table, keys: SqlLoader(table, keys, source),
        )
        app.ejecutar()
        with source.begin() as connection:
            connection.execute(update(OpinionModel).where(OpinionModel.IdOrigen == "W0001").values(IdOrigen="CSV_WEB"))
        rerun = app.ejecutar()
        self.assertEqual(rerun["insertados"], 0)
        self.assertEqual(rerun["rechazados"], 582)
        first = sincronizar_warehouse(source, warehouse)
        second = sincronizar_warehouse(source, warehouse)
        self.assertEqual(first["hechos_totales"], 318)
        self.assertEqual(first["hechos_insertados"], 318)
        self.assertEqual(first["predicciones_nuevas"], 312)
        self.assertEqual(second["hechos_insertados"], 0)
        self.assertEqual(second["predicciones_nuevas"], 0)
        with source.connect() as connection:
            self.assertEqual(connection.scalar(select(func.count()).select_from(AnalisisOpinionModel)), 312)
            self.assertEqual(connection.scalar(select(func.count()).select_from(OpinionModel).where(OpinionModel.IdClasificacion.is_not(None))), 6)
            ids = set(connection.scalars(select(OpinionModel.IdOrigen)))
            self.assertNotIn("CSV_WEB", ids)
            self.assertIn("W0001", ids)
        with warehouse.connect() as connection:
            self.assertEqual(connection.scalar(select(func.count()).select_from(FactOpinion)), 318)
        kpis = obtener_kpis(warehouse)
        self.assertEqual(sum(row["total"] for row in kpis), 318)
        self.assertEqual(sum(row["positivas"] + row["negativas"] + row["neutras"] for row in kpis), 318)


if __name__ == "__main__":
    unittest.main()
