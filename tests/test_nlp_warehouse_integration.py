"""Integración NLP: procedencia, lotes, versión e idempotencia en SQLite."""

import unittest
from datetime import date
from math import nan

from sqlalchemy import create_engine, func, insert, select

from application.interfaces.services.ISentimentClassifier import ISentimentClassifier
from application.services.lexicon_classifier import LexiconClassifier
from application.services.sentiment import Prediccion, VERSION
from infrastructure.composition import create_sentiment_classifier
from infrastructure.persistence import models as src
from infrastructure.persistence.warehouse import FactOpinion
from infrastructure.services.WarehouseSync import _predecir_pendientes, sincronizar_warehouse


class StubClassifier(ISentimentClassifier):
    def __init__(self, results):
        self.results = results
        self.calls = []

    def predict_batch(self, comments, batch_size=16):
        self.calls.append((list(comments), batch_size))
        return self.results


class NLPWarehouseIntegrationTests(unittest.TestCase):
    def test_production_composition_keeps_validated_baseline(self):
        self.assertIsInstance(create_sentiment_classifier(), LexiconClassifier)

    def setUp(self):
        self.source = create_engine("sqlite:///:memory:")
        self.warehouse = create_engine("sqlite:///:memory:")
        self.addCleanup(self.source.dispose)
        self.addCleanup(self.warehouse.dispose)
        src.Base.metadata.create_all(self.source)
        with self.source.begin() as connection:
            connection.execute(insert(src.CategoriaModel),
                               [{"IdCategoria": 1, "Nombre": "Tecnología"}])
            connection.execute(insert(src.ClasificacionModel), [
                {"IdClasificacion": 1, "Tipo": "Positiva"},
                {"IdClasificacion": 2, "Tipo": "Negativa"},
                {"IdClasificacion": 3, "Tipo": "Neutra"},
            ])
            connection.execute(insert(src.TipoOpinionModel),
                               [{"IdTipoOpinion": 2, "Nombre": "Reseña"}])
            connection.execute(insert(src.FuenteDatosModel),
                               [{"IdFuente": 1, "TipoFuente": "Web"}])
            connection.execute(insert(src.ClienteModel),
                               [{"IdCliente": 1, "Nombre": "Ana", "email": "ana@example.com"}])
            connection.execute(insert(src.ProductoModel),
                               [{"IdProducto": 1, "Nombre": "Equipo", "IdCategoria": 1}])
            common = {"Fecha": date(2026, 11, 11), "IdCliente": 1, "IdProducto": 1,
                      "IdFuente": 1, "IdTipoOpinion": 2, "Canal": "Web",
                      "IdClasificacion": None}
            connection.execute(insert(src.OpinionModel), [
                {**common, "IdOpinion": 101, "IdOrigen": "W101", "Comentario": "Bueno",
                 "IdClasificacion": 1},
                {**common, "IdOpinion": 102, "IdOrigen": "W102", "Comentario": "Excelente"},
                {**common, "IdOpinion": 103, "IdOrigen": "W103", "Comentario": "Malo"},
                {**common, "IdOpinion": 104, "IdOrigen": "W104", "Comentario": "Informativo"},
            ])
            connection.execute(insert(src.AnalisisOpinionModel), [
                {"IdOpinion": 104, "IdClasificacion": 3, "Confianza": 0.5,
                 "ModeloVersion": "version-anterior"},
            ])

    def test_injected_classifier_only_processes_missing_and_preserves_provenance(self):
        classifier = StubClassifier([Prediccion(2, 0.8, "modelo-prueba-v1"),
                                     Prediccion(1, 0.7, "modelo-prueba-v1")])
        first = sincronizar_warehouse(self.source, self.warehouse, classifier)
        self.assertEqual(classifier.calls, [(["Excelente", "Malo"], 16)])
        self.assertEqual(first["predicciones_nuevas"], 2)
        with self.source.connect() as connection:
            analyses = {row["IdOpinion"]: row for row in connection.execute(
                select(src.AnalisisOpinionModel.__table__)).mappings()}
            self.assertNotIn(101, analyses)
            self.assertEqual(analyses[102]["ModeloVersion"], "modelo-prueba-v1")
            self.assertEqual(analyses[102]["Confianza"], 0.8)
            self.assertEqual(analyses[104]["ModeloVersion"], "version-anterior")
            self.assertEqual(connection.scalar(select(src.OpinionModel.IdClasificacion)
                                               .where(src.OpinionModel.IdOpinion == 101)), 1)
        with self.warehouse.connect() as connection:
            classes = dict(connection.execute(
                select(FactOpinion.IdOpinion, FactOpinion.IdClasificacion)).all())
            self.assertEqual(classes, {101: 1, 102: 2, 103: 1, 104: 3})

        unused = StubClassifier([Prediccion(3, 1.0, "otro-modelo")])
        second = sincronizar_warehouse(self.source, self.warehouse, unused)
        self.assertEqual(unused.calls, [])
        self.assertEqual(second["predicciones_nuevas"], 0)
        self.assertEqual(second["hechos_insertados"], 0)

    def test_invalid_batch_is_rejected_before_writing(self):
        bad = StubClassifier([Prediccion(2, 0.8, "incompleto")])
        with self.assertRaisesRegex(ValueError, "una predicción por opinión"):
            sincronizar_warehouse(self.source, self.warehouse, bad)
        with self.source.connect() as connection:
            self.assertEqual(connection.scalar(select(func.count()).select_from(
                src.AnalisisOpinionModel)), 1)

        pending = [{"IdOpinion": 1, "IdClasificacion": None,
                    "Prediccion": None, "Comentario": "Texto"}]
        for result in (Prediccion(4, 0.5, "v1"), Prediccion(1, nan, "v1"),
                       Prediccion(1, 0.5, "x" * 51)):
            with self.subTest(result=result), self.assertRaises(ValueError):
                _predecir_pendientes(pending, StubClassifier([result]))
            self.assertIsNone(pending[0]["Prediccion"])
        with self.assertRaisesRegex(ValueError, "resultado inválido"):
            _predecir_pendientes(pending, StubClassifier([None]))
        pending[0]["Comentario"] = "  "
        with self.assertRaisesRegex(ValueError, "sin comentario válido"):
            _predecir_pendientes(pending, StubClassifier([Prediccion(3, 0, VERSION)]))


if __name__ == "__main__":
    unittest.main()
