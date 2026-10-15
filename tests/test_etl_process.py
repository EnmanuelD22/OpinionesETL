"""Pruebas de contrato y de integración local del ETL."""

#region Imports
import unittest
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from application.exceptions.etl_exceptions import TransformationError
from application.interfaces.services.IExtractor import IExtractor
from application.interfaces.services.ILoader import ILoader
from application.models.etl_results import CatalogContext
from application.models.schema import DataSchema, FieldRule
from application.services.DataTransformer import DataTransformer
from application.services.etl_pipeline import ETLPipeline
from application.services.pipeline_factory import build_etl_application
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.services.SqlCatalogService import SqlCatalogService
from infrastructure.services.sqlLoader import SqlLoader
#endregion


#region Test doubles
class MemoryExtractor(IExtractor):
    def __init__(self, data: pd.DataFrame):
        self.data = data

    def extract(self) -> pd.DataFrame:
        return self.data.copy()


class MemoryLoader(ILoader):
    def __init__(self):
        self.loaded = 0

    def cargar(self, df: pd.DataFrame):
        self.loaded += len(df)
        return len(df), 0
#endregion


#region Tests
class ETLProcessTests(unittest.TestCase):
    def test_transformer_rejects_duplicates_and_reports_reasons(self):
        transformer = DataTransformer(
            columnas_requeridas=["IdCliente", "Nombre"],
            clave_duplicados=["IdCliente"],
        )
        datos = pd.DataFrame({
            "IdCliente": [1, 1, 2],
            "Nombre": ["Ana", "Ana", ""],
        })

        validos, rechazados = transformer.transformar(datos)

        self.assertEqual(len(validos), 1)
        self.assertEqual(rechazados, 2)
        self.assertEqual(
            transformer.last_rejection_reasons,
            {"registro_duplicado": 1, "campo_obligatorio_vacio": 1},
        )

    def test_transformer_raises_when_required_column_is_missing(self):
        transformer = DataTransformer(["IdCliente", "Nombre"])

        with self.assertRaises(TransformationError):
            transformer.transformar(pd.DataFrame({"IdCliente": [1]}))

    def test_schema_validates_dates_scores_and_references(self):
        transformer = DataTransformer(
            ["IdCliente", "Fecha", "Puntaje"],
            ["IdCliente", "Fecha"],
            referencias={"IdCliente": {1}},
            esquema=DataSchema.from_rules([
                FieldRule("IdCliente", "integer"),
                FieldRule("Fecha", "date"),
                FieldRule("Puntaje", "number", minimum=1, maximum=5),
            ]),
        )
        datos = pd.DataFrame({
            "IdCliente": [1, 2, 1],
            "Fecha": ["fecha-invalida", "2025-01-01", "2025-01-02"],
            "Puntaje": [3, 3, 6],
        })

        validos, rechazados = transformer.transformar(datos)

        self.assertEqual(len(validos), 0)
        self.assertEqual(rechazados, 3)
        self.assertEqual(
            transformer.last_rejection_reasons,
            {
                "fecha_invalida_o_vacia": 1,
                "integridad_referencial": 1,
                "puntaje_invalido": 1,
            },
        )

    def test_pipeline_uses_injected_ports_and_returns_metrics(self):
        loader = MemoryLoader()
        pipeline = ETLPipeline(
            "Prueba en memoria",
            MemoryExtractor(pd.DataFrame({"IdCliente": [1, 1], "Nombre": ["Ana", "Ana"]})),
            DataTransformer(["IdCliente", "Nombre"], ["IdCliente"]),
            loader,
        )

        result = pipeline.ejecutar()

        self.assertEqual(result, {"procesados": 2, "insertados": 1, "rechazados": 1})
        self.assertEqual(loader.loaded, 1)
        self.assertEqual(pipeline.last_result.rejection_reasons, {"registro_duplicado": 1})

    def test_complete_process_runs_against_sqlite_without_sql_server(self):
        data_dir = Path(__file__).resolve().parents[1] / "data"
        db_engine = create_engine("sqlite:///:memory:")
        application = build_etl_application(
            data_dir=data_dir,
            catalog_service=SqlCatalogService(
                db_engine,
                CsvExtractor(data_dir / "products.csv"),
            ),
            extractor_factory=CsvExtractor,
            loader_factory=lambda table, keys: SqlLoader(
                table,
                keys,
                db_engine=db_engine,
            ),
        )

        result = application.ejecutar()

        self.assertEqual(
            result,
            {"procesados": 1700, "insertados": 1118, "rechazados": 582},
        )
#endregion


if __name__ == "__main__":
    unittest.main()
