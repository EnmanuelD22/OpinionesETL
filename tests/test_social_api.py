"""Contrato HTTP y paginación de la API social sin SQL Server."""

import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.pool import StaticPool

from api import create_app
from infrastructure.persistence.base import Base
from infrastructure.persistence.models import AnalisisOpinionModel, OpinionModel


def memory_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


class SocialApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = memory_engine()
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for opinion in [
                {"IdOpinion": 1, "IdOrigen": "T1", "IdTipoOpinion": 3,
                 "IdCliente": 10, "IdProducto": 20, "Fecha": date(2025, 1, 2),
                 "Comentario": "Primer comentario", "IdFuente": 5,
                 "Canal": "Redes Sociales", "Puntaje": None,
                 "IdClasificacion": None},
                {"IdOpinion": 2, "IdOrigen": "W1", "IdTipoOpinion": 2,
                 "Comentario": "Reseña", "Fecha": date(2025, 1, 3)},
                {"IdOpinion": 3, "IdOrigen": "T3", "IdTipoOpinion": 3,
                 "Comentario": "Segundo comentario", "Fecha": date(2025, 1, 4),
                 "IdClasificacion": 1},
                {"IdOpinion": 5, "IdOrigen": "T5", "IdTipoOpinion": 3,
                 "Comentario": "Tercer comentario", "Fecha": date(2025, 1, 5)},
            ]:
                connection.execute(insert(OpinionModel).values(**opinion))
            connection.execute(insert(AnalisisOpinionModel), [
                {"IdOpinion": 1, "IdClasificacion": 2,
                 "Confianza": 0.8, "ModeloVersion": "prueba"},
            ])
        self.client = TestClient(create_app(self.engine))

    def test_filters_social_rows_and_pages_by_stable_id(self):
        first = self.client.get("/api/v1/comentarios-sociales", params={"limit": 1})
        self.assertEqual(first.status_code, 200)
        body = first.json()
        self.assertEqual([item["IdOpinion"] for item in body["items"]], [1])
        self.assertTrue(body["has_more"])
        self.assertEqual(body["next_after_id"], 1)
        self.assertEqual(body["items"][0]["Fecha"], "2025-01-02")
        self.assertEqual(body["items"][0]["IdClasificacionPredicha"], 2)
        self.assertIsNone(body["items"][0]["IdClasificacionOriginal"])
        self.assertNotIn("Nombre", body["items"][0])
        self.assertNotIn("email", body["items"][0])

        second = self.client.get(
            "/api/v1/comentarios-sociales", params={"after_id": 1, "limit": 1}
        ).json()
        self.assertEqual([item["IdOpinion"] for item in second["items"]], [3])
        self.assertEqual(second["items"][0]["IdClasificacionOriginal"], 1)
        self.assertEqual(second["next_after_id"], 3)

        last = self.client.get(
            "/api/v1/comentarios-sociales", params={"after_id": 3, "limit": 1}
        ).json()
        self.assertEqual([item["IdOpinion"] for item in last["items"]], [5])
        self.assertFalse(last["has_more"])
        self.assertIsNone(last["next_after_id"])

        empty = self.client.get(
            "/api/v1/comentarios-sociales", params={"after_id": 5}
        ).json()
        self.assertEqual(empty, {"items": [], "next_after_id": None, "has_more": False})

    def test_rejects_invalid_pagination(self):
        for params in ({"after_id": -1}, {"limit": 0}, {"limit": 501}):
            with self.subTest(params=params):
                response = self.client.get("/api/v1/comentarios-sociales", params=params)
                self.assertEqual(response.status_code, 422)

    def test_reports_database_error(self):
        unavailable = memory_engine()
        self.addCleanup(unavailable.dispose)
        with self.assertLogs("api", level="ERROR"):
            response = TestClient(create_app(unavailable)).get(
                "/api/v1/comentarios-sociales"
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Base relacional no disponible")


if __name__ == "__main__":
    unittest.main()
