"""Contrato y rechazos de la preparación selectiva."""

import csv
import unittest
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine, select

from application.services.analytic_preparation import (
    AnalyticCatalog, AnalyticPreparation, SetBasedAnalyticPreparation,
)
from infrastructure.services.AnalyticStagingWriter import AnalyticStagingWriter
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.services.SetBasedStagingWriter import SetBasedStagingWriter


class Extractor:
    def __init__(self, rows):
        self.rows = rows

    def extract(self):
        return pd.DataFrame(self.rows)


class CatalogReader:
    def read(self):
        return AnalyticCatalog({1}, {2}, {2, 3}, {1, 2, 3}, {"7": 101})


class CollectingWriter:
    def write(self, batch_id, opinions, rejections):
        self.batch_id = batch_id
        self.opinions = opinions
        self.rejections = rejections


class CollectingSetWriter:
    def write_set_based(self, batch_id, surveys, social, rejections, survey_mode):
        self.surveys = surveys
        self.social = social
        self.rejections = rejections
        self.mode = survey_mode
        return {"resena": {"leidos": 2, "preparados": 2, "rechazados": 0},
                "encuesta_modo": "batch"}


class AnalyticPreparationTests(unittest.TestCase):
    def test_selects_sources_and_keeps_row_rejections(self):
        surveys = Extractor([
            {"IdOpinion": 7, "IdCliente": 1, "IdProducto": 2,
             "Fecha": "2025-01-01", "Comentario": "Bien", "Clasificación": "Positiva",
             "PuntajeSatisfacción": 5, "Fuente": "EncuestaInterna"},
            {"IdOpinion": 8, "IdCliente": 99, "IdProducto": 2,
             "Fecha": "2025-01-01", "Comentario": "Mal", "Clasificación": "Negativa",
             "PuntajeSatisfacción": 2, "Fuente": "EncuestaInterna"},
        ])
        common = {"IdCliente": 1, "IdProducto": 2, "Fecha": date(2025, 1, 2),
                  "Comentario": "Opinión", "IdFuente": 3, "Canal": "web",
                  "IdClasificacionOriginal": None, "IdClasificacionPredicha": 2}
        reviews = Extractor([{**common, "IdOpinion": 102, "IdOrigen": "R1",
                              "IdTipoOpinion": 2, "Puntaje": 4}])
        social = Extractor([{**common, "IdOpinion": 103, "IdOrigen": "S1",
                             "IdTipoOpinion": 3, "Puntaje": None},
                            {**common, "IdOpinion": 104, "IdOrigen": "S2",
                             "IdTipoOpinion": 3, "Puntaje": None,
                             "IdClasificacionPredicha": "incorrecta"},
                            {**common, "IdOpinion": 105, "IdOrigen": "S3",
                             "IdTipoOpinion": 3, "Puntaje": "abc"},
                            {**common, "IdOpinion": 106, "IdOrigen": "S4",
                             "IdTipoOpinion": 3, "Puntaje": None,
                             "IdClasificacionPredicha": None},
                            {**common, "IdOpinion": 107, "IdOrigen": "S1",
                             "IdTipoOpinion": 3, "Puntaje": None}])
        writer = CollectingWriter()
        result = AnalyticPreparation(surveys, reviews, social,
                                     CatalogReader(), writer).run()

        self.assertEqual(result["preparados"], 3)
        self.assertEqual(result["rechazados"], 5)
        self.assertEqual(result["fuentes"]["encuesta"],
                         {"leidos": 2, "preparados": 1, "rechazados": 1})
        self.assertEqual({row["IdTipoOpinion"] for row in writer.opinions}, {1, 2, 3})
        self.assertEqual(next(row for row in writer.opinions
                              if row["IdTipoOpinion"] == 1)["IdOpinion"], 101)
        self.assertEqual(next(row for row in writer.opinions
                              if row["IdTipoOpinion"] == 3)["Puntaje"], None)
        self.assertEqual({row["Motivo"] for row in writer.rejections},
                         {"integridad_referencial", "clasificacion_invalida",
                          "puntaje_invalido", "sin_clasificacion_valida",
                          "registro_duplicado"})
        self.assertTrue(any(row["Motivo"] == "registro_duplicado"
                            for row in writer.rejections))

    def test_staging_writer_replaces_only_its_batch(self):
        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        metadata = MetaData()
        opinion = Table("Stg_Opinion", metadata,
                        Column("IdEjecucion", String, primary_key=True),
                        Column("IdTipoOpinion", Integer, primary_key=True),
                        Column("IdOrigen", String, primary_key=True),
                        Column("IdOpinion", Integer), Column("Fecha", Date),
                        Column("Puntaje", Float))
        rejection = Table("Stg_Rechazo", metadata,
                          Column("IdRechazo", Integer, primary_key=True),
                          Column("IdEjecucion", String), Column("Origen", String),
                          Column("IdOrigen", String), Column("Motivo", String))
        metadata.create_all(engine)
        batch_id = str(uuid4())
        rows = [{"IdEjecucion": batch_id, "IdTipoOpinion": 1,
                 "IdOrigen": "7", "IdOpinion": 101, "Fecha": date(2025, 1, 1),
                 "Puntaje": 5.0}]
        rejects = [{"IdEjecucion": batch_id, "Origen": "encuesta",
                    "IdOrigen": "8", "Motivo": "integridad_referencial"}]
        writer = AnalyticStagingWriter(engine)
        writer.write(batch_id, rows, rejects)
        writer.write(batch_id, rows, rejects)
        with engine.connect() as connection:
            self.assertEqual(len(connection.execute(select(opinion)).all()), 1)
            self.assertEqual(len(connection.execute(select(rejection)).all()), 1)

    def test_set_based_flow_delegates_reviews_and_writes_prepared_csv(self):
        survey = Extractor([{
            "IdOpinion": 7, "IdCliente": 1, "IdProducto": 2,
            "Fecha": "2025-01-01", "Comentario": 'Bien, "excelente"',
            "Clasificación": "Positiva", "PuntajeSatisfacción": 5,
        }])
        social = Extractor([{
            "IdOpinion": 103, "IdOrigen": "S1", "IdTipoOpinion": 3,
            "IdCliente": 1, "IdProducto": 2, "Fecha": "2025-01-02",
            "Comentario": "Opinión", "IdFuente": 3, "Canal": "social",
            "Puntaje": None, "IdClasificacionOriginal": None,
            "IdClasificacionPredicha": 2,
        }])
        writer = CollectingSetWriter()
        result = SetBasedAnalyticPreparation(
            survey, social, CatalogReader(), writer
        ).run(survey_mode="batch")
        self.assertEqual(result["preparados"], 4)
        self.assertEqual(result["fuentes"]["resena"]["leidos"], 2)
        self.assertEqual(len(writer.surveys), 1)
        self.assertEqual(len(writer.social), 1)
        self.assertEqual(writer.mode, "batch")

        with TemporaryDirectory() as directory:
            path = SetBasedStagingWriter(None, directory)._survey_csv(writer.surveys)
            with path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[1][5], 'Bien, "excelente"')
            self.assertEqual(len(rows[1]), 12)
            self.assertNotIn(b"\r\n", path.read_bytes())

    def test_tvp_transport_uses_zero_for_optional_nulls(self):
        class Cursor:
            def execute(self, statement, batch_id, tvp):
                self.tvp = tvp

        cursor = Cursor()
        row = dict(zip(
            ("IdOrigen", "IdOpinion", "IdCliente", "IdProducto", "Fecha",
             "Comentario", "IdFuente", "Canal", "Puntaje",
             "IdClasificacionOriginal", "IdClasificacionPredicha", "IdClasificacion"),
            ("S1", 103, 1, 2, date(2025, 1, 2), "Opinión", 3, "social",
             None, None, 2, 2),
        ))
        SetBasedStagingWriter._insert_social_tvp(cursor, str(uuid4()), [row])
        self.assertEqual(cursor.tvp[2][8:11], (0, 0, 2))

    def test_survey_csv_preserves_source_id_as_text(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "surveys.csv"
            path.write_text("IdOpinion,IdCliente\n007,1\n", encoding="utf-8")
            frame = CsvExtractor(path, dtypes={"IdOpinion": "string"}).extract()
            self.assertEqual(frame.iloc[0]["IdOpinion"], "007")

    def test_long_survey_id_is_preserved_in_rejection(self):
        source_id = "E" * 80
        survey = Extractor([{
            "IdOpinion": source_id, "IdCliente": 1, "IdProducto": 2,
            "Fecha": "2025-01-01", "Comentario": "Texto",
            "Clasificación": "Positiva", "PuntajeSatisfacción": 5,
        }])
        rows, rejected, counts = AnalyticPreparation._prepare_source(
            "encuesta", 1, survey, CatalogReader().read(), str(uuid4())
        )
        self.assertEqual(rows, [])
        self.assertEqual(counts["rechazados"], 1)
        self.assertEqual(rejected[0]["IdOrigen"], source_id)
        self.assertEqual(rejected[0]["Motivo"], "longitud_excedida")


if __name__ == "__main__":
    unittest.main()
