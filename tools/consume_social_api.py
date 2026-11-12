"""Comprueba la lectura paginada de la API social sin escribir en SQL Server."""

import argparse
import os

from infrastructure.services.ApiExtractor import ApiExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SOCIAL_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()
    rows = ApiExtractor(args.url, page_size=args.page_size).extract()
    print(f"Comentarios sociales recibidos: {len(rows)}")
    if not rows.empty:
        print(f"IdOpinion: {rows.iloc[0]['IdOpinion']} a {rows.iloc[-1]['IdOpinion']}")


if __name__ == "__main__":
    main()
