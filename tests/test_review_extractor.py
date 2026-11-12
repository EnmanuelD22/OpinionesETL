"""Pruebas de la consulta selectiva de reseñas relacionales."""

import unittest
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, insert

from application.exceptions.etl_exceptions import ExtractionError
from infrastructure.persistence.base import Base
from infrastructure.persistence.models import AnalisisOpinionModel, OpinionModel
from infrastructure.services.OpinionReviewExtractor import (
    REVIEW_COLUMNS, OpinionReviewExtractor,
)


class OpinionReviewExtractorTests(unittest.TestCase):
    def test_filters_type_two_and_preserves_classification_provenance(self):
        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            for opinion in [
                {"IdOpinion": 1, "IdOrigen": "W1", "IdTipoOpinion": 2,
                 "IdCliente": 7, "IdProducto": 8, "IdFuente": 1,
                 "Fecha": date(2025, 1, 1), "Comentario": "Reseña uno",
                 "Canal": "Reseñas Web", "Puntaje": 4,
                 "IdClasificacion": None},
                {"IdOpinion": 2, "IdOrigen": "T1", "IdTipoOpinion": 3,
                 "Fecha": date(2025, 1, 2), "Comentario": "Comentario social"},
                {"IdOpinion": 3, "IdOrigen": "W3", "IdTipoOpinion": 2,
                 "Fecha": date(2025, 1, 3), "Comentario": "Reseña tres",
                 "Puntaje": 5, "IdClasificacion": 1},
            ]:
                connection.execute(insert(OpinionModel).values(**opinion))
            connection.execute(insert(AnalisisOpinionModel), [
                {"IdOpinion": 1, "IdClasificacion": 2,
                 "Confianza": 0.8, "ModeloVersion": "prueba"},
            ])

        rows = OpinionReviewExtractor(engine).extract()

        self.assertEqual(list(rows.columns), list(REVIEW_COLUMNS))
        self.assertEqual(rows["IdOpinion"].tolist(), [1, 3])
        self.assertEqual(rows["IdTipoOpinion"].tolist(), [2, 2])
        self.assertEqual(rows.iloc[0]["IdClasificacionPredicha"], 2)
        self.assertTrue(pd.isna(rows.iloc[0]["IdClasificacionOriginal"]))
        self.assertEqual(rows.iloc[1]["IdClasificacionOriginal"], 1)

    def test_missing_opinion_table_raises_extraction_error(self):
        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        with self.assertRaises(ExtractionError):
            OpinionReviewExtractor(engine).extract()


if __name__ == "__main__":
    unittest.main()
