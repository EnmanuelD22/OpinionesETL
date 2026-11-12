"""Mide 50 000 comentarios sintéticos a través del extractor HTTP paginado."""

import tracemalloc
from time import perf_counter

import httpx

from infrastructure.services.ApiExtractor import ApiExtractor


def main():
    count = 50_000
    pages = 0

    def handler(request):
        nonlocal pages
        pages += 1
        after = int(request.url.params["after_id"])
        limit = int(request.url.params["limit"])
        end = min(after + limit, count)
        items = [
            {"IdOpinion": i, "IdOrigen": f"PERF50K_{i:05d}",
             "IdTipoOpinion": 3, "IdCliente": 1, "IdProducto": 1,
             "Fecha": "2025-01-01", "Comentario": f"Comentario sintético {i}",
             "IdFuente": 5, "Canal": "Redes Sociales", "Puntaje": None,
             "IdClasificacionOriginal": 1, "IdClasificacionPredicha": None}
            for i in range(after + 1, end + 1)
        ]
        return httpx.Response(200, json={"items": items,
                                          "has_more": end < count,
                                          "next_after_id": end if end < count else None})

    tracemalloc.start()
    started = perf_counter()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ApiExtractor("http://synthetic.test", client=client).extract()
    seconds = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    ids = result["IdOpinion"]
    if len(ids) != count or ids.iloc[0] != 1 or ids.iloc[-1] != count or ids.nunique() != count:
        raise AssertionError("Paginación de 50 000 opiniones incompleta o duplicada")
    print({"comentarios": count, "paginas": pages,
           "segundos": round(seconds, 3), "memoria_pico_mib": round(peak / 2**20, 2)})


if __name__ == "__main__":
    main()
