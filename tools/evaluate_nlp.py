"""Perfila fuentes y evalúa la línea base NLP sin entrenar un modelo.

Uso: python -m tools.evaluate_nlp --data-dir data --report reports/nlp_baseline.json
La plantilla de anotación se guarda en evaluation/private/ (ignorada por Git).
"""

import argparse
import csv
import hashlib
import json
import random
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from application.services.sentiment import VERSION, clasificar

LABELS = {"Positiva": 1, "Negativa": 2, "Neutra": 3}
SOURCES = (
    ("Encuesta", "surveys_part1.csv", "IdOpinion", "Clasificación"),
    ("Social", "social_comments.csv", "IdComment", None),
    ("Web", "web_reviews.csv", "IdReview", None),
)


def canonical(text: str) -> str:
    """Clave de agrupación de textos idénticos sin cambiar el texto evaluado."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def sample_id(text: str) -> str:
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


def validate_output_paths(data_dir: Path, *outputs: Path) -> None:
    """Impide sobrescribir accidentalmente fuentes CSV del maestro."""
    source_dir = data_dir.resolve()
    for output in outputs:
        if output.resolve().is_relative_to(source_dir):
            raise ValueError(f"La salida no puede ubicarse dentro de las fuentes: {output}")


def load_sources(data_dir: Path) -> list[dict]:
    records = []
    for channel, filename, id_column, label_column in SOURCES:
        with (data_dir / filename).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {id_column, "Comentario"} | ({label_column} if label_column else set())
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f"Columnas faltantes en {filename}: {sorted(required - set(reader.fieldnames or []))}")
            for row in reader:
                comment = (row["Comentario"] or "").strip()
                label = (row[label_column] or "").strip() if label_column else ""
                records.append({"canal": channel, "id_origen": row[id_column],
                                "comentario": comment, "etiqueta_origen": label,
                                "grupo": sample_id(comment) if comment else ""})
    return records


def scores(true_labels: list[int], predictions: list[int]) -> dict:
    if len(true_labels) != len(predictions):
        raise ValueError("Cantidad distinta de etiquetas y predicciones")
    if not true_labels:
        return {"n": 0, "accuracy": None, "macro_f1": None, "por_clase": {}}
    by_class = {}
    for name, label in LABELS.items():
        tp = sum(a == label and b == label for a, b in zip(true_labels, predictions))
        fp = sum(a != label and b == label for a, b in zip(true_labels, predictions))
        fn = sum(a == label and b != label for a, b in zip(true_labels, predictions))
        support = sum(a == label for a in true_labels)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        by_class[name] = {"support": support, "precision": round(precision, 4),
                          "recall": round(recall, 4), "f1": round(f1, 4)}
    return {"n": len(true_labels),
            "accuracy": round(sum(a == b for a, b in zip(true_labels, predictions)) / len(true_labels), 4),
            "macro_f1": round(sum(v["f1"] for v in by_class.values()) / len(LABELS), 4),
            "por_clase": by_class}


def profile(records: list[dict]) -> dict:
    result = {}
    for channel, *_ in SOURCES:
        rows = [r for r in records if r["canal"] == channel]
        usable = [r for r in rows if r["grupo"]]
        unique = len({r["grupo"] for r in usable})
        result[channel] = {"filas": len(rows), "comentarios_no_vacios": len(usable),
                           "textos_unicos": unique, "repeticiones": len(usable) - unique,
                           "etiquetas_origen": dict(sorted(Counter(r["etiqueta_origen"] for r in rows if r["etiqueta_origen"]).items()))}
    result["global"] = {"filas": len(records),
                        "textos_unicos": len({r["grupo"] for r in records if r["grupo"]})}
    return result


def baseline_survey(records: list[dict]) -> dict:
    labeled = [r for r in records if r["canal"] == "Encuesta" and r["grupo"]]
    unknown = sorted({r["etiqueta_origen"] for r in labeled} - LABELS.keys())
    if unknown:
        raise ValueError(f"Etiquetas desconocidas: {unknown}")
    all_scores = scores([LABELS[r["etiqueta_origen"]] for r in labeled],
                        [clasificar(r["comentario"]).id_clasificacion for r in labeled])
    groups = defaultdict(list)
    for row in labeled:
        groups[row["grupo"]].append(row)
    conflicts = sum(len({r["etiqueta_origen"] for r in rows}) > 1 for rows in groups.values())
    unique_rows = [rows[0] for rows in groups.values()
                   if len({r["etiqueta_origen"] for r in rows}) == 1]
    unique_scores = scores([LABELS[r["etiqueta_origen"]] for r in unique_rows],
                           [clasificar(r["comentario"]).id_clasificacion for r in unique_rows])
    return {"filas_etiquetadas": all_scores, "textos_unicos_etiquetados": unique_scores,
            "grupos_con_etiquetas_conflictivas": conflicts,
            "uso": "diagnostico_del_fixture; no es validacion fuera de muestra"}


def annotation_rows(records: list[dict], limit: int, seed: int) -> list[dict]:
    """Muestra por canal, con un único registro por texto normalizado."""
    groups = {}
    channels = defaultdict(set)
    for row in records:
        if row["grupo"]:
            groups.setdefault(row["grupo"], row["comentario"])
            channels[row["grupo"]].add(row["canal"])
    randomizer = random.Random(seed)
    pools = {}
    for channel, *_ in SOURCES:
        ids = sorted(group for group, source_channels in channels.items() if channel in source_channels)
        randomizer.shuffle(ids)
        pools[channel] = ids
    selected = []
    seen = set()
    while len(selected) < limit and any(pools.values()):
        for channel, *_ in SOURCES:
            while pools[channel] and pools[channel][0] in seen:
                pools[channel].pop(0)
            if pools[channel] and len(selected) < limit:
                group = pools[channel].pop(0)
                seen.add(group)
                selected.append({"sample_id": group, "canales": ",".join(sorted(channels[group])),
                                 "comentario": groups[group], "etiqueta_revisada": "", "anotador": ""})
    return selected


def evaluate_reviewed(path: Path, expected: dict[str, set[str]]) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [row.get("sample_id", "") for row in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(expected):
        raise ValueError("IDs de anotación duplicados o ajenos a las fuentes")
    if any(row.get("comentario") and sample_id(row["comentario"]) != row["sample_id"] for row in rows):
        raise ValueError("El texto de una anotación cambió respecto de su sample_id")
    labeled = [row for row in rows if row.get("etiqueta_revisada", "").strip()]
    invalid = {row["etiqueta_revisada"].strip() for row in labeled} - LABELS.keys()
    if invalid:
        raise ValueError(f"Etiquetas revisadas inválidas: {sorted(invalid)}")
    if not all(row.get("comentario", "").strip() for row in labeled):
        raise ValueError("Hay anotaciones sin comentario")
    def measure(subset):
        return scores([LABELS[row["etiqueta_revisada"].strip()] for row in subset],
                      [clasificar(row["comentario"]).id_clasificacion for row in subset])
    return {"global": measure(labeled), "por_canal": {
        channel: measure([row for row in labeled if channel in expected[row["sample_id"]]])
        for channel, *_ in SOURCES}, "pendientes": len(rows) - len(labeled),
        "anotadores_declarados": sorted({row.get("anotador", "").strip() for row in labeled
                                         if row.get("anotador", "").strip()}),
        "uso": "diagnostico del fixture; requiere revisión humana independiente para validar calidad"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--report", type=Path, default=Path("reports/nlp_baseline.json"))
    parser.add_argument("--annotation-output", type=Path, default=Path("evaluation/private/annotation_queue.csv"))
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reviewed", type=Path)
    parser.add_argument("--overwrite-queue", action="store_true",
                        help="Reemplaza la plantilla; nunca usar sobre anotaciones revisadas")
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size debe ser positivo")
    validate_output_paths(args.data_dir, args.report, args.annotation_output)
    records = load_sources(args.data_dir)
    queue = annotation_rows(records, args.sample_size, args.seed)
    report = {"version_clasificador": VERSION, "fuentes": profile(records),
              "linea_base_encuestas": baseline_survey(records),
              "muestra_para_revision": len(queue),
              "reproducibilidad": {
                  "semilla": args.seed, "tamano_solicitado": args.sample_size,
                  "sha256_fuentes": {
                      filename: hashlib.sha256((args.data_dir / filename).read_bytes()).hexdigest()
                      for _, filename, _, _ in SOURCES
                  },
              }}
    if args.reviewed:
        expected = defaultdict(set)
        for row in records:
            if row["grupo"]:
                expected[row["grupo"]].add(row["canal"])
        report["evaluacion_revisada"] = evaluate_reviewed(args.reviewed, expected)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.annotation_output.parent.mkdir(parents=True, exist_ok=True)
    if args.reviewed and args.reviewed.resolve() == args.annotation_output.resolve():
        parser.error("--reviewed y --annotation-output deben ser archivos distintos")
    if not args.annotation_output.exists() or args.overwrite_queue:
        with args.annotation_output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("sample_id", "canales", "comentario",
                                                      "etiqueta_revisada", "anotador"))
            writer.writeheader()
            writer.writerows(queue)
        print(f"Reporte: {args.report} | Muestra privada: {args.annotation_output}")
    else:
        print(f"Reporte: {args.report} | Muestra existente preservada: {args.annotation_output}")


if __name__ == "__main__":
    main()
