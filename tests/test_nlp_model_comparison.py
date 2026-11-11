"""Contratos del candidato y comparación, sin red ni pesos descargados."""

import csv
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from application.services.lexicon_classifier import LexiconClassifier
from infrastructure.services.ProductReviewClassifier import (
    MODEL_VERSION, ProductReviewClassifier, STAR_LABELS,
)
from tools.compare_nlp_models import compare, evaluate_rows, load_review
from tools.evaluate_nlp import LABELS, SOURCES, load_sources


ROOT = Path(__file__).resolve().parents[1]


class NLPCandidateTests(unittest.TestCase):
    def test_lexicon_contract_preserves_order_and_rejects_invalid_inputs(self):
        classifier = LexiconClassifier()
        result = classifier.predict_batch(["Excelente", "Malo", "Sin detalles"], 2)
        self.assertEqual([item.id_clasificacion for item in result], [1, 2, 3])
        with self.assertRaises(ValueError):
            classifier.predict_batch([""], 2)
        with self.assertRaises(ValueError):
            classifier.predict_batch(["Texto"], 0)

    def test_review_model_groups_star_probabilities_in_input_order(self):
        class FakeTensor:
            def __init__(self, values):
                self.values = values

            def tolist(self):
                return self.values

        class FakeTokenizer:
            def __call__(self, texts, **options):
                self.options = options
                return {"texts": texts}

        class FakeModel:
            config = SimpleNamespace(id2label=STAR_LABELS)

            def __call__(self, texts):
                vectors = {"bueno": [0.05, 0.05, 0.1, 0.35, 0.45],
                           "malo": [0.4, 0.3, 0.2, 0.05, 0.05],
                           "informativo": [0.05, 0.05, 0.7, 0.1, 0.1]}
                return SimpleNamespace(logits=[vectors[text] for text in texts])

        candidate = object.__new__(ProductReviewClassifier)
        candidate.torch = SimpleNamespace(inference_mode=nullcontext,
                                          softmax=lambda logits, dim: FakeTensor(logits))
        candidate.tokenizer = FakeTokenizer()
        candidate.model = FakeModel()
        result = candidate.predict_batch(["bueno", "malo", "informativo"], 2)
        self.assertEqual([item.id_clasificacion for item in result], [1, 2, 3])
        self.assertEqual([item.version for item in result], [MODEL_VERSION] * 3)
        self.assertEqual(result[1].confianza, 0.7)
        self.assertEqual(candidate.tokenizer.options["max_length"], 128)
        with self.assertRaises(ValueError):
            candidate.predict_batch([" "])
        with self.assertRaises(ValueError):
            candidate.predict_batch(["bueno"], 0)

    def test_comparison_checks_sources_annotations_and_output_lengths(self):
        records = load_sources(ROOT / "data")
        expected = {}
        source_texts = {}
        for row in records:
            if row["grupo"]:
                expected.setdefault(row["grupo"], set()).add(row["canal"])
                source_texts.setdefault(row["grupo"], set()).add(row["comentario"])
        reviewed = ROOT / "evaluation" / "revision_fixture.csv"
        rows = load_review(reviewed, expected, source_texts)
        self.assertEqual(len(rows), 45)
        self.assertEqual(set(LABELS), {row["etiqueta_revisada"] for row in rows})

        with self.assertRaises(ValueError):
            evaluate_rows(rows, expected, [])
        with self.assertRaises(ValueError):
            evaluate_rows(rows, expected,
                          [SimpleNamespace(id_clasificacion=9)] * len(rows))

        class FakeCandidate:
            def predict_batch(self, comments, batch_size=16):
                return LexiconClassifier().predict_batch(comments, batch_size)

        scratch = ROOT / "evaluation" / "private"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            report = Path(folder) / "comparison.json"
            result = compare(ROOT / "data", reviewed, report, 8, candidate=FakeCandidate())
            self.assertEqual(result["lexico"]["metricas"]["global"]["n"], 45)
            self.assertEqual(result["lexico"]["metricas"], result["modelo_resenas"]["metricas"])
            self.assertEqual({channel: result["modelo_resenas"]["metricas"]["por_canal"][channel]["n"]
                              for channel, *_ in SOURCES},
                             {"Encuesta": 15, "Social": 15, "Web": 15})
            saved = report.read_text(encoding="utf-8")
            self.assertNotIn(rows[0]["comentario"], saved)
            self.assertEqual(json.loads(saved)["entradas"]["comentarios"], 45)
            with self.assertRaises(ValueError):
                compare(ROOT / "data", reviewed, reviewed, 8, candidate=FakeCandidate())
            with self.assertRaises(ValueError):
                compare(ROOT / "data", reviewed, ROOT / "data" / "report.json", 8,
                        candidate=FakeCandidate())

            invalid = Path(folder) / "invalid.csv"
            with invalid.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerow({**rows[0], "comentario": "Texto ajeno"})
            with self.assertRaises(ValueError):
                load_review(invalid, expected, source_texts)
            invalid.write_text(",".join(rows[0].keys()) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_review(invalid, expected, source_texts)


if __name__ == "__main__":
    unittest.main()
