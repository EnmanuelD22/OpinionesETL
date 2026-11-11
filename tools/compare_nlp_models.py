"""Compara línea base y candidato local sobre etiquetas revisadas.

Uso: python -m tools.compare_nlp_models
No altera CSV de origen, AnalisisOpinion ni el DW.
"""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from application.services.lexicon_classifier import LexiconClassifier
from infrastructure.services.ProductReviewClassifier import (
    MODEL_ID, MODEL_REVISION, ProductReviewClassifier,
)
from tools.evaluate_nlp import (
    LABELS, SOURCES, load_sources, sample_id, scores, validate_output_paths,
)


def evaluate_rows(rows: list[dict], expected: dict[str, set[str]], predictions) -> dict:
    if len(predictions) != len(rows):
        raise ValueError("El clasificador no devolvió una predicción por comentario")
    true_labels = [LABELS[row["etiqueta_revisada"]] for row in rows]
    values = [prediction.id_clasificacion for prediction in predictions]
    if any(value not in LABELS.values() for value in values):
        raise ValueError("El clasificador devolvió una clase desconocida")
    return {"global": scores(true_labels, values), "por_canal": {
        channel: scores(
            [truth for row, truth in zip(rows, true_labels) if channel in expected[row["sample_id"]]],
            [value for row, value in zip(rows, values) if channel in expected[row["sample_id"]]],
        ) for channel, *_ in SOURCES
    }}


def load_review(path: Path, expected: dict[str, set[str]],
                source_texts: dict[str, set[str]]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [row.get("sample_id", "") for row in rows]
    if not rows or len(ids) != len(set(ids)) or not set(ids).issubset(expected):
        raise ValueError("IDs duplicados o ajenos a las fuentes")
    if any(sample_id(row.get("comentario", "")) != row["sample_id"] for row in rows):
        raise ValueError("Hay comentarios modificados después de generar sample_id")
    if any(row["comentario"] not in source_texts[row["sample_id"]] for row in rows):
        raise ValueError("La revisión contiene textos que no están en las fuentes")
    if any(row.get("etiqueta_revisada", "") not in LABELS for row in rows):
        raise ValueError("La comparación requiere todas las etiquetas revisadas")
    return rows


def compare(data_dir: Path, reviewed: Path, report: Path, batch_size: int,
            candidate: ProductReviewClassifier | None = None, offline: bool = False) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size debe ser positivo")
    validate_output_paths(data_dir, report)
    if report.resolve() == reviewed.resolve():
        raise ValueError("El reporte no puede sobrescribir las etiquetas revisadas")
    records = load_sources(data_dir)
    expected = defaultdict(set)
    source_texts = defaultdict(set)
    for row in records:
        if row["grupo"]:
            expected[row["grupo"]].add(row["canal"])
            source_texts[row["grupo"]].add(row["comentario"])
    rows = load_review(reviewed, expected, source_texts)
    comments = [row["comentario"] for row in rows]
    baseline_start = perf_counter()
    baseline = LexiconClassifier().predict_batch(comments, batch_size)
    baseline_seconds = perf_counter() - baseline_start
    load_start = perf_counter()
    classifier = candidate if candidate is not None else ProductReviewClassifier(local_files_only=offline)
    load_seconds = perf_counter() - load_start
    candidate_start = perf_counter()
    predictions = classifier.predict_batch(comments, batch_size)
    candidate_seconds = perf_counter() - candidate_start
    output = {
        "evaluacion": "textos únicos con etiquetas revisadas; representatividad e independencia requieren verificación externa",
        "modelo_candidato": {"id": MODEL_ID, "revision": MODEL_REVISION,
                              "version": predictions[0].version if predictions else None},
        "entradas": {"comentarios": len(rows), "batch_size": batch_size,
                     "sha256_revision": hashlib.sha256(reviewed.read_bytes()).hexdigest(),
                     "sha256_fuentes": {
                         filename: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest()
                         for _, filename, _, _ in SOURCES
                     }},
        "lexico": {"metricas": evaluate_rows(rows, expected, baseline),
                   "segundos_inferencia": round(baseline_seconds, 4)},
        "modelo_resenas": {"metricas": evaluate_rows(rows, expected, predictions),
                           "segundos_carga": round(load_seconds, 4),
                           "segundos_inferencia": round(candidate_seconds, 4)},
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--reviewed", type=Path, default=Path("evaluation/revision_fixture.csv"))
    parser.add_argument("--report", type=Path, default=Path("reports/nlp_model_comparison.json"))
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--offline", action="store_true",
                        help="Usa únicamente los pesos ya descargados en .cache/huggingface")
    args = parser.parse_args()
    result = compare(args.data_dir, args.reviewed, args.report, args.batch_size,
                     offline=args.offline)
    print(f"Comparación guardada: {args.report}")
    for name in ("lexico", "modelo_resenas"):
        metric = result[name]["metricas"]["global"]
        print(f"{name}: accuracy={metric['accuracy']:.4f}, macro_f1={metric['macro_f1']:.4f}")


if __name__ == "__main__":
    main()
