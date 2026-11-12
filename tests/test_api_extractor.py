"""Contrato HTTP de la extracción social."""

import unittest

import httpx

from application.exceptions.etl_exceptions import ExtractionError
from infrastructure.services.ApiExtractor import ApiExtractor


def social_row(opinion_id: int) -> dict:
    return {
        "IdOpinion": opinion_id, "IdOrigen": f"T{opinion_id:04}",
        "IdTipoOpinion": 3, "IdCliente": 1, "IdProducto": 1,
        "Fecha": "2025-01-01", "Comentario": "Comentario de prueba",
        "IdFuente": 5, "Canal": "Redes Sociales", "Puntaje": None,
        "IdClasificacionOriginal": None, "IdClasificacionPredicha": 3,
    }


class ApiExtractorTests(unittest.TestCase):
    def test_reads_all_pages_in_order(self):
        cursors = []

        def handler(request):
            cursor = int(request.url.params["after_id"])
            cursors.append(cursor)
            if cursor == 0:
                return httpx.Response(200, json={"items": [social_row(2), social_row(5)],
                                                 "has_more": True, "next_after_id": 5})
            return httpx.Response(200, json={"items": [social_row(8)],
                                             "has_more": False, "next_after_id": None})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rows = ApiExtractor("http://testserver", page_size=2, client=client).extract()
        self.assertEqual(cursors, [0, 5])
        self.assertEqual(rows["IdOpinion"].tolist(), [2, 5, 8])
        self.assertEqual(set(rows["IdTipoOpinion"]), {3})

    def test_rejects_nonprogressing_page(self):
        def handler(request):
            return httpx.Response(200, json={"items": [social_row(2)],
                                             "has_more": True, "next_after_id": 0})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ExtractionError, "sin avance"):
                ApiExtractor("http://testserver", client=client).extract()

    def test_http_error_is_not_an_empty_batch(self):
        with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(503)
        )) as client:
            with self.assertRaises(ExtractionError):
                ApiExtractor("http://testserver", client=client).extract()

    def test_nullable_business_date_remains_available_for_row_validation(self):
        row = social_row(4)
        row["Fecha"] = None
        with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={
                "items": [row], "has_more": False, "next_after_id": None,
            })
        )) as client:
            rows = ApiExtractor("http://testserver", client=client).extract()
        self.assertIsNone(rows.iloc[0]["Fecha"])


if __name__ == "__main__":
    unittest.main()
