"""Contrato de orquestación del lote analítico."""

import unittest
from unittest.mock import Mock

from application.exceptions.etl_exceptions import PersistenceError
from infrastructure.services.AnalyticWarehouseLoader import (
    AnalyticWarehouseLoader, PROCEDURES,
)


BATCH = "31a8d32b-f73b-46b7-bb18-9b16f103bf7a"


class WarehouseLoaderTests(unittest.TestCase):
    def setUp(self):
        self.engine = Mock()
        self.connection = self.engine.raw_connection.return_value
        self.cursor = self.connection.cursor.return_value

    def test_runs_dimensions_before_fact_and_returns_counts(self):
        self.cursor.fetchone.side_effect = [(318, 318)] + [(318, 0, 0)] * 6 + [(318, 0, 0, 318)]
        self.cursor.description = [("Leidos",), ("Insertados",),
                                   ("Actualizados",), ("SinCambios",)]
        result = AnalyticWarehouseLoader(self.engine).load(BATCH)
        executed = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertEqual([f"EXEC dbo.{name} @IdEjecucion = ?"
                          for _, name in PROCEDURES], executed[1:])
        self.assertEqual(318, result["procedimientos"]["fact_opinion"]["Leidos"])
        self.assertEqual(1, self.connection.commit.call_count)
        self.connection.close.assert_called_once()

    def test_empty_batch_never_calls_procedures(self):
        self.cursor.fetchone.return_value = (0, 0)
        with self.assertRaises(PersistenceError):
            AnalyticWarehouseLoader(self.engine).load(BATCH)
        self.assertEqual(1, self.cursor.execute.call_count)
        self.connection.rollback.assert_called_once()

    def test_later_procedure_failure_rolls_back_whole_batch(self):
        self.cursor.fetchone.side_effect = [(1, 1), (1, 0, 0), RuntimeError("fallo")]
        self.cursor.description = [("ClavesLote",), ("Insertadas",), ("Actualizadas",)]
        with self.assertRaisesRegex(RuntimeError, "fallo"):
            AnalyticWarehouseLoader(self.engine).load(BATCH)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
