"""Extractor paginado de comentarios sociales desde la API del proyecto."""

from datetime import date

import httpx
import pandas as pd

from application.exceptions.etl_exceptions import ExtractionError
from application.interfaces.services.IExtractor import IExtractor


SOCIAL_COLUMNS = (
    "IdOpinion", "IdOrigen", "IdTipoOpinion", "IdCliente", "IdProducto",
    "Fecha", "Comentario", "IdFuente", "Canal", "Puntaje",
    "IdClasificacionOriginal", "IdClasificacionPredicha",
)


class ApiExtractor(IExtractor):
    """Lee todas las páginas sociales sin omitir ni repetir claves."""

    def __init__(self, base_url: str, page_size: int = 100, timeout: float = 10.0,
                 client: httpx.Client | None = None):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url debe ser una URL HTTP")
        if not 1 <= page_size <= 500:
            raise ValueError("page_size debe estar entre 1 y 500")
        self.url = f"{base_url.rstrip('/')}/api/v1/comentarios-sociales"
        self.page_size = page_size
        self.timeout = timeout
        self.client = client

    def extract(self) -> pd.DataFrame:
        client = self.client or httpx.Client(timeout=self.timeout)
        rows: list[dict] = []
        after_id = 0
        try:
            while True:
                response = client.get(
                    self.url, params={"after_id": after_id, "limit": self.page_size},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                page = response.json()
                if not isinstance(page, dict):
                    raise ValueError("La API devolvió una página no válida")
                items = page.get("items")
                has_more = page.get("has_more")
                next_id = page.get("next_after_id")
                if not isinstance(items, list) or type(has_more) is not bool:
                    raise ValueError("La API devolvió metadatos de página inválidos")
                if len(items) > self.page_size:
                    raise ValueError("La API excedió el tamaño de página solicitado")

                previous_id = after_id
                for item in items:
                    if not isinstance(item, dict) or set(SOCIAL_COLUMNS) - item.keys():
                        raise ValueError("La API devolvió un comentario incompleto")
                    opinion_id = item["IdOpinion"]
                    if type(opinion_id) is not int or opinion_id <= previous_id:
                        raise ValueError("La API devolvió IdOpinion fuera de orden")
                    if item["IdTipoOpinion"] != 3:
                        raise ValueError("La API devolvió una opinión no social")
                    if item["Fecha"] is not None:
                        try:
                            date.fromisoformat(item["Fecha"])
                        except (TypeError, ValueError) as error:
                            raise ValueError("La API devolvió una fecha inválida") from error
                    rows.append({column: item[column] for column in SOCIAL_COLUMNS})
                    previous_id = opinion_id

                if not has_more:
                    if next_id is not None:
                        raise ValueError("La última página debe tener next_after_id nulo")
                    break
                if not items or type(next_id) is not int or next_id != previous_id:
                    raise ValueError("La API devolvió una paginación sin avance")
                after_id = next_id
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise ExtractionError(f"No fue posible extraer comentarios sociales: {error}") from error
        finally:
            if self.client is None:
                client.close()

        return pd.DataFrame(rows, columns=SOCIAL_COLUMNS)
