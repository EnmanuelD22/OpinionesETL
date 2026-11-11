"""Evalúa evidencia para promover un clasificador; nunca modifica el ETL ni SQL."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from infrastructure.services.ProductReviewClassifier import MODEL_ID, MODEL_REVISION, MODEL_VERSION
from tools.compare_nlp_models import load_review
from tools.evaluate_nlp import LABELS, SOURCES, load_sources, validate_output_paths

MIN_PER_CHANNEL = 100
MIN_PER_CLASS_CHANNEL = 20
MIN_BENCHMARK_RECORDS = 50_000
MAX_BENCHMARK_SECONDS = 300


def review_evidence(data_dir: Path, final_path: Path, reviewer_a: Path | None,
                    reviewer_b: Path | None) -> tuple[list[str], dict]:
    reasons = []
    expected = defaultdict(set)
    source_texts = defaultdict(set)
    for row in load_sources(data_dir):
        if row["grupo"]:
            expected[row["grupo"]].add(row["canal"])
            source_texts[row["grupo"]].add(row["comentario"])
    final = load_review(final_path, expected, source_texts)
    by_id = {row["sample_id"]: row for row in final}
    counts = {channel: {label: 0 for label in LABELS} for channel, *_ in SOURCES}
    for row in final:
        for channel in expected[row["sample_id"]]:
            counts[channel][row["etiqueta_revisada"]] += 1
    for channel, labels in counts.items():
        if sum(labels.values()) < MIN_PER_CHANNEL:
            reasons.append(f"{channel}: menos de {MIN_PER_CHANNEL} textos únicos")
        for label, count in labels.items():
            if count < MIN_PER_CLASS_CHANNEL:
                reasons.append(f"{channel}/{label}: menos de {MIN_PER_CLASS_CHANNEL} textos")

    if reviewer_a is None or reviewer_b is None:
        reasons.append("Faltan dos revisiones humanas independientes")
    else:
        first = load_review(reviewer_a, expected, source_texts)
        second = load_review(reviewer_b, expected, source_texts)
        reviewers = []
        for rows in (first, second):
            identities = {row.get("anotador", "").strip() for row in rows}
            if len(identities) != 1 or not next(iter(identities)):
                reasons.append("Cada archivo debe identificar a un solo revisor")
            reviewers.append(identities)
            if {row["sample_id"] for row in rows} != set(by_id):
                reasons.append("Los revisores y la adjudicación deben cubrir los mismos textos")
        if len(reviewers[0]) == len(reviewers[1]) == 1 and reviewers[0] == reviewers[1]:
            reasons.append("Los dos revisores deben tener identificadores distintos")
        a = {row["sample_id"]: row for row in first}
        b = {row["sample_id"]: row for row in second}
        for sample in set(by_id) & set(a) & set(b):
            if (a[sample]["etiqueta_revisada"] == b[sample]["etiqueta_revisada"]
                    and by_id[sample]["etiqueta_revisada"] != a[sample]["etiqueta_revisada"]):
                reasons.append("La adjudicación contradice una coincidencia de revisores")
                break
    return reasons, {"textos_unicos": len(final), "por_canal_y_clase": counts}


def comparison_evidence(path: Path, data_dir: Path, final_path: Path,
                        expected_count: int | None = None) -> list[str]:
    if not path.exists():
        return ["Falta el reporte comparativo de ambos modelos"]
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["El reporte comparativo no es JSON válido"]
    if not isinstance(result, dict):
        return ["El reporte comparativo carece de métricas válidas"]
    candidate = result.get("modelo_candidato", {})
    if not isinstance(candidate, dict):
        return ["El reporte comparativo carece de métricas válidas"]
    if (candidate.get("id"), candidate.get("revision"), candidate.get("version")) != (
            MODEL_ID, MODEL_REVISION, MODEL_VERSION):
        return ["La comparación no corresponde a la versión candidata fijada"]
    inputs = result.get("entradas", {})
    if not isinstance(inputs, dict):
        return ["El reporte comparativo carece de métricas válidas"]
    if inputs.get("sha256_revision") != hashlib.sha256(final_path.read_bytes()).hexdigest():
        return ["La comparación no corresponde a las etiquetas finales"]
    source_hashes = {filename: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest()
                     for _, filename, _, _ in SOURCES}
    if inputs.get("sha256_fuentes") != source_hashes:
        return ["La comparación no corresponde a las fuentes evaluadas"]
    if expected_count is not None and inputs.get("comentarios") != expected_count:
        return ["La comparación no cubre todas las etiquetas finales"]
    reasons = []
    try:
        baseline = result["lexico"]["metricas"]
        candidate_metrics = result["modelo_resenas"]["metricas"]
        for channel in ("global", *(channel for channel, *_ in SOURCES)):
            current = baseline["global"] if channel == "global" else baseline["por_canal"][channel]
            proposed = (candidate_metrics["global"] if channel == "global"
                        else candidate_metrics["por_canal"][channel])
            if current["n"] != proposed["n"] or proposed["n"] == 0:
                reasons.append(f"{channel}: cobertura de evaluación inválida")
                continue
            if proposed["macro_f1"] < current["macro_f1"]:
                reasons.append(f"{channel}: F1 macro del candidato inferior a la línea base")
            if (proposed["por_clase"]["Negativa"]["recall"]
                    < current["por_clase"]["Negativa"]["recall"]):
                reasons.append(f"{channel}: recall negativo del candidato inferior a la línea base")
    except (KeyError, TypeError, ValueError):
        return ["El reporte comparativo carece de métricas válidas"]
    return reasons


def performance_evidence(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return ["Falta evidencia de rendimiento del ETL completo en SQL Server"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["El reporte de rendimiento no es JSON válido"]
    if not isinstance(data, dict):
        return ["El reporte de rendimiento no identifica ejecución, datos y modelo"]
    if (data.get("motor") != "SQL Server" or data.get("alcance") != "ETL completo"
            or data.get("modelo_version") != MODEL_VERSION
            or not isinstance(data.get("dataset_sha256"), str)
            or len(data["dataset_sha256"]) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in data["dataset_sha256"])):
        return ["El reporte de rendimiento no identifica ejecución, datos y modelo"]
    rows, seconds = data.get("comentarios"), data.get("segundos")
    if (type(rows) is not int or rows < MIN_BENCHMARK_RECORDS
            or type(seconds) not in (int, float) or not 0 < seconds <= MAX_BENCHMARK_SECONDS):
        return ["El rendimiento no acredita 50.000 comentarios en 300 segundos"]
    return []


def assess(data_dir: Path, final_path: Path, comparison_path: Path,
           reviewer_a: Path | None = None, reviewer_b: Path | None = None,
           performance_path: Path | None = None) -> dict:
    review_reasons, coverage = review_evidence(data_dir, final_path, reviewer_a, reviewer_b)
    quality_reasons = review_reasons + comparison_evidence(
        comparison_path, data_dir, final_path, coverage["textos_unicos"]
    )
    performance_reasons = performance_evidence(performance_path)
    return {"calidad_aprobada": not quality_reasons,
            "aprobado": not quality_reasons and not performance_reasons,
            "modelo_version": MODEL_VERSION, "cobertura": coverage,
            "motivos_calidad": quality_reasons,
            "motivos_rendimiento": performance_reasons,
            "motivos": quality_reasons + performance_reasons,
            "nota": "Control estructural; requiere confirmar la independencia humana y la medición SQL Server"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--final", type=Path, default=Path("evaluation/revision_fixture.csv"))
    parser.add_argument("--reviewer-a", type=Path)
    parser.add_argument("--reviewer-b", type=Path)
    parser.add_argument("--comparison", type=Path, default=Path("reports/nlp_model_comparison.json"))
    parser.add_argument("--performance", type=Path)
    parser.add_argument("--stage", choices=("quality", "final"), default="final",
                        help="quality evalúa etiquetas y métricas; final exige además rendimiento")
    parser.add_argument("--report", type=Path, default=Path("reports/nlp_release_gate.json"))
    args = parser.parse_args()
    validate_output_paths(args.data_dir, args.report)
    if args.report.resolve() in {path.resolve() for path in (
            args.final, args.reviewer_a, args.reviewer_b, args.comparison, args.performance)
            if path is not None}:
        parser.error("El reporte no puede sobrescribir archivos de evidencia")
    result = assess(args.data_dir, args.final, args.comparison,
                    args.reviewer_a, args.reviewer_b, args.performance)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    passed = result["calidad_aprobada"] if args.stage == "quality" else result["aprobado"]
    print(f"Etapa {args.stage}: {'APROBADA' if passed else 'NO APROBADA'}")
    reasons = result["motivos_calidad"] if args.stage == "quality" else result["motivos"]
    for reason in reasons:
        print(f"- {reason}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
