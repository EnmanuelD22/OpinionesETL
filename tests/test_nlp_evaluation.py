"""Pruebas de métricas y muestreo para la evaluación NLP."""

import csv
import tempfile
import unittest
from pathlib import Path

from tools.evaluate_nlp import (
    annotation_rows, baseline_survey, canonical, evaluate_reviewed,
    load_sources, profile, sample_id, scores, validate_output_paths,
)


class NLPEvaluationTests(unittest.TestCase):
    def test_profile_and_baseline_distinguish_rows_from_unique_texts(self):
        records = load_sources(Path(__file__).resolve().parents[1] / "data")
        summary = profile(records)
        self.assertEqual(summary["global"]["filas"], 900)
        self.assertEqual(summary["global"]["textos_unicos"], 45)
        self.assertEqual(summary["Encuesta"]["textos_unicos"], 15)
        baseline = baseline_survey(records)
        self.assertEqual(baseline["filas_etiquetadas"]["n"], 500)
        self.assertEqual(baseline["textos_unicos_etiquetados"]["n"], 15)

    def test_sample_groups_equal_text_and_covers_channels(self):
        text = "Gran relación calidad-precio"
        records = [
            {"canal": "Encuesta", "comentario": text, "grupo": sample_id(text)},
            {"canal": "Web", "comentario": "  GRAN  RELACIÓN CALIDAD-PRECIO ",
             "grupo": sample_id("  GRAN  RELACIÓN CALIDAD-PRECIO ")},
            {"canal": "Social", "comentario": "Mala calidad", "grupo": sample_id("Mala calidad")},
        ]
        queue = annotation_rows(records, 10, 42)
        self.assertEqual(len(queue), 2)
        self.assertEqual(len({row["sample_id"] for row in queue}), 2)
        self.assertIn("Encuesta,Web", {row["canales"] for row in queue})
        self.assertEqual(canonical("  GRAN  RELACIÓN "), canonical("gran relación"))

    def test_metrics_and_reviewed_input_validation(self):
        metrics = scores([1, 2, 3], [1, 3, 3])
        self.assertAlmostEqual(metrics["accuracy"], 0.6667, places=4)
        self.assertEqual(metrics["por_clase"]["Negativa"]["recall"], 0)
        scratch = Path(__file__).resolve().parents[1] / "evaluation" / "private"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            path = Path(folder) / "reviewed.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["sample_id", "comentario", "etiqueta_revisada"])
                writer.writeheader()
                writer.writerow({"sample_id": sample_id("Muy mala calidad"),
                                 "comentario": "Muy mala calidad", "etiqueta_revisada": "Negativa"})
            expected = {sample_id("Muy mala calidad"): {"Social"}}
            evaluation = evaluate_reviewed(path, expected)
            self.assertEqual(evaluation["global"]["n"], 1)
            self.assertEqual(evaluation["por_canal"]["Social"]["n"], 1)
            with path.open("a", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([sample_id("Muy mala calidad"), "Muy mala calidad", "Positiva"])
            with self.assertRaises(ValueError):
                evaluate_reviewed(path, expected)

    def test_source_directory_cannot_be_an_output(self):
        source = Path(__file__).resolve().parents[1] / "data"
        with self.assertRaises(ValueError):
            validate_output_paths(source, source / "surveys_part1.csv")

    def test_fixture_review_covers_every_unique_text_and_channel(self):
        root = Path(__file__).resolve().parents[1]
        records = load_sources(root / "data")
        expected = {}
        for row in records:
            if row["grupo"]:
                expected.setdefault(row["grupo"], set()).add(row["canal"])
        result = evaluate_reviewed(root / "evaluation" / "revision_fixture.csv", expected)
        self.assertEqual(result["global"]["n"], 45)
        self.assertEqual(result["pendientes"], 0)
        self.assertEqual({channel: value["n"] for channel, value in result["por_canal"].items()},
                         {"Encuesta": 15, "Social": 15, "Web": 15})


if __name__ == "__main__":
    unittest.main()
