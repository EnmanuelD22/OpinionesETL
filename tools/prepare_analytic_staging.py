"""Prepara fuentes selectivas y, opcionalmente, carga dimensiones y FACT."""

import argparse
import json
import logging
import os
from pathlib import Path

from application.services.analytic_preparation import (
    AnalyticPreparation, SetBasedAnalyticPreparation,
)
from infrastructure.database import get_dw_engine, get_engine
from infrastructure.services.AnalyticCatalogReader import AnalyticCatalogReader
from infrastructure.services.ApiExtractor import ApiExtractor
from infrastructure.services.CsvExtractor import CsvExtractor
from infrastructure.services.OpinionReviewExtractor import OpinionReviewExtractor
from infrastructure.services.SetBasedStagingWriter import SetBasedStagingWriter
from infrastructure.services.AnalyticWarehouseLoader import AnalyticWarehouseLoader


ROOT = Path(__file__).resolve().parents[1]


class PreviewWriter:
    """Permite inspeccionar conteos sin modificar OpinionesDW."""

    def write(self, batch_id: str, opinions: list[dict], rejections: list[dict]) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.getenv("SOCIAL_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--batch-id", help="UUID para reintentar el mismo lote")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validar fuentes y contar filas sin escribir en staging")
    parser.add_argument("--load", action="store_true",
                        help="Tras preparar staging, ejecutar dimensiones y FACT")
    parser.add_argument("--load-existing-batch", metavar="UUID",
                        help="Cargar dimensiones y FACT desde un lote ya preparado")
    parser.add_argument("--survey-mode", choices=("auto", "bulk", "batch"),
                        default="auto", help="Estrategia de carga para las encuestas")
    parser.add_argument("--bulk-dir", type=Path, default=ROOT / "tmp" / "bulk",
                        help="Directorio temporal que SQL Server puede leer")
    args = parser.parse_args()
    if args.dry_run and (args.load or args.load_existing_batch):
        parser.error("--dry-run no se combina con carga de dimensiones o FACT")
    if args.load_existing_batch and args.batch_id:
        parser.error("--load-existing-batch ya identifica el lote")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    relational = get_engine()
    warehouse = get_dw_engine()
    try:
        if args.load_existing_batch:
            result = {"IdEjecucion": args.load_existing_batch,
                      "carga_dw": AnalyticWarehouseLoader(warehouse).load(args.load_existing_batch)}
        elif args.dry_run:
            preparation = AnalyticPreparation(
                CsvExtractor(ROOT / "data" / "surveys_part1.csv",
                             dtypes={"IdOpinion": "string"}),
                OpinionReviewExtractor(relational),
                ApiExtractor(args.api_url),
                AnalyticCatalogReader(relational),
                PreviewWriter(),
            )
            result = preparation.run(args.batch_id)
        else:
            preparation = SetBasedAnalyticPreparation(
                CsvExtractor(ROOT / "data" / "surveys_part1.csv",
                             dtypes={"IdOpinion": "string"}),
                ApiExtractor(args.api_url),
                AnalyticCatalogReader(relational),
                SetBasedStagingWriter(warehouse, args.bulk_dir),
            )
            result = preparation.run(args.batch_id, survey_mode=args.survey_mode)
            if args.load:
                result["carga_dw"] = AnalyticWarehouseLoader(warehouse).load(
                    result["IdEjecucion"]
                )
        result["solo_validacion"] = args.dry_run
        logging.info("Preparación selectiva: %s", json.dumps(result, ensure_ascii=False))
    finally:
        warehouse.dispose()


if __name__ == "__main__":
    main()
