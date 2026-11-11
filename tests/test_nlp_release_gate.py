"""El control de promoción falla cerrado con evidencia incompleta o inconsistente."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.nlp_release_gate import (
    MODEL_VERSION, assess, comparison_evidence, performance_evidence, review_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


class NLPReleaseGateTests(unittest.TestCase):
    def test_academic_fixture_cannot_promote_candidate(self):
        result = assess(ROOT / "data", ROOT / "evaluation/revision_fixture.csv",
                        ROOT / "reports/nlp_model_comparison.json")
        self.assertFalse(result["aprobado"])
        self.assertFalse(result["calidad_aprobada"])
        self.assertEqual(result["cobertura"]["textos_unicos"], 45)
        self.assertTrue(any("F1 macro" in reason for reason in result["motivos"]))
        self.assertTrue(any("revisiones humanas" in reason for reason in result["motivos"]))
        self.assertTrue(any("rendimiento" in reason for reason in result["motivos"]))
        self.assertFalse(any("rendimiento" in reason for reason in result["motivos_calidad"]))
        self.assertNotIn("Comentario", json.dumps(result))

    def test_reviewer_identifiers_and_source_hashes_are_checked(self):
        scratch = ROOT / "evaluation/private"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            folder = Path(folder)
            original = ROOT / "evaluation/revision_fixture.csv"
            with original.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            paths = []
            for name in ("A", "B"):
                path = folder / f"review_{name}.csv"
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows([{**row, "anotador": name} for row in rows])
                paths.append(path)
            reasons, coverage = review_evidence(ROOT / "data", original, *paths)
            self.assertEqual(coverage["textos_unicos"], 45)
            self.assertFalse(any("revisor" in reason.lower() for reason in reasons))
            same, _ = review_evidence(ROOT / "data", original, paths[0], paths[0])
            self.assertTrue(any("distintos" in reason for reason in same))

            comparison = json.loads((ROOT / "reports/nlp_model_comparison.json").read_text(encoding="utf-8"))
            comparison["entradas"]["sha256_revision"] = "0" * 64
            altered = folder / "comparison.json"
            altered.write_text(json.dumps(comparison), encoding="utf-8")
            errors = comparison_evidence(altered, ROOT / "data", original)
            self.assertTrue(any("etiquetas finales" in reason for reason in errors))
            altered.write_text(json.dumps({"modelo_candidato": [], "entradas": {}}),
                               encoding="utf-8")
            self.assertTrue(comparison_evidence(altered, ROOT / "data", original))

    def test_performance_requires_full_sql_server_measurement(self):
        scratch = ROOT / "evaluation/private"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            report = Path(folder) / "performance.json"
            valid = {"motor": "SQL Server", "alcance": "ETL completo",
                     "modelo_version": MODEL_VERSION, "dataset_sha256": "a" * 64,
                     "comentarios": 50_000, "segundos": 300}
            report.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(performance_evidence(report), [])
            valid["segundos"] = 301
            report.write_text(json.dumps(valid), encoding="utf-8")
            self.assertTrue(performance_evidence(report))
            valid["segundos"] = 200
            valid["motor"] = "SQLite"
            report.write_text(json.dumps(valid), encoding="utf-8")
            self.assertTrue(performance_evidence(report))


if __name__ == "__main__":
    unittest.main()
