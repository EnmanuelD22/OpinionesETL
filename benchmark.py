"""Mide el proceso completo en la instancia SQL Server configurada."""

import argparse
from time import perf_counter

from main import main


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-records", type=int, default=50000)
    parser.add_argument("--max-seconds", type=float, default=300)
    args = parser.parse_args()
    start = perf_counter()
    result = main()
    seconds = perf_counter() - start
    print(f"Procesados: {result['procesados']} | Segundos: {seconds:.2f}")
    if result["procesados"] < args.min_records:
        raise SystemExit("Muestra insuficiente para certificar la meta de rendimiento")
    if seconds > args.max_seconds:
        raise SystemExit("No se cumplió la meta de rendimiento")


if __name__ == "__main__":
    run()
