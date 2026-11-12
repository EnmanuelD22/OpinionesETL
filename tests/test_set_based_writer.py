"""Decisión BULK y reversión de la alternativa por lotes, sin SQL Server."""

import tempfile
import unittest
from datetime import date

import pyodbc

from application.exceptions.etl_exceptions import PersistenceError
from infrastructure.services.SetBasedStagingWriter import SetBasedStagingWriter


BATCH_ID = "00000000-0000-4000-8000-000000000012"
SURVEY = {
    "IdOrigen": "7", "IdOpinion": 101, "IdCliente": 1, "IdProducto": 2,
    "Fecha": date(2026, 11, 11), "Comentario": "Encuesta válida",
    "IdFuente": 2, "Canal": "Encuestas", "Puntaje": 5.0,
    "IdClasificacionOriginal": 1, "IdClasificacionPredicha": None,
    "IdClasificacion": 1,
}


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.fast_executemany = False
        self.last_result = None

    def execute(self, statement, *params):
        self.connection.events.append(("execute", statement, params))
        if "usp_CargarEncuestasBulkStaging" in statement:
            if self.connection.bulk_error is not None:
                raise self.connection.bulk_error
            self.last_result = (1,)
        elif "usp_PrepararResenasRelacionales" in statement:
            self.last_result = (2, 2, 0)
        else:
            self.last_result = None
        return self

    def fetchone(self):
        return self.last_result

    def executemany(self, statement, rows):
        self.connection.events.append(
            ("executemany", statement, list(rows), self.fast_executemany)
        )
        return self


class FakeConnection:
    def __init__(self, bulk_error=None):
        self.bulk_error = bulk_error
        self.events = []

    def cursor(self):
        self.events.append(("cursor",))
        return FakeCursor(self)

    def rollback(self):
        self.events.append(("rollback",))

    def commit(self):
        self.events.append(("commit",))

    def close(self):
        self.events.append(("close",))


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    def raw_connection(self):
        return self.connection


class SetBasedWriterTests(unittest.TestCase):
    def _writer(self, connection):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return SetBasedStagingWriter(FakeEngine(connection), directory.name)

    def test_auto_prefers_bulk_when_sql_server_can_open_file(self):
        connection = FakeConnection()
        writer = self._writer(connection)
        result = writer.write_set_based(
            BATCH_ID, [SURVEY], [], [], survey_mode="auto"
        )
        self.assertEqual(result["encuesta_modo"], "bulk")
        self.assertTrue(any("usp_CargarEncuestasBulkStaging" in event[1]
                            for event in connection.events if event[0] == "execute"))
        self.assertFalse(any(event[0] == "executemany" for event in connection.events))
        self.assertEqual(sum(event[0] == "commit" for event in connection.events), 1)
        self.assertEqual(list(writer.bulk_dir.glob("*.csv")), [])

    def test_auto_retries_with_fast_executemany_only_for_file_access_error(self):
        error = pyodbc.OperationalError(
            "42000", "Cannot bulk load because the file could not be opened. (4860)"
        )
        connection = FakeConnection(bulk_error=error)
        writer = self._writer(connection)
        result = writer.write_set_based(
            BATCH_ID, [SURVEY], [], [], survey_mode="auto"
        )
        self.assertEqual(result["encuesta_modo"], "batch")
        self.assertEqual(sum(event[0] == "rollback" for event in connection.events), 1)
        self.assertEqual(sum(event[0] == "commit" for event in connection.events), 1)
        deletes = [event for event in connection.events
                   if event[0] == "execute" and event[1].startswith("DELETE FROM")]
        self.assertEqual(len(deletes), 4)
        inserts = [event for event in connection.events if event[0] == "executemany"]
        self.assertEqual(len(inserts), 1)
        self.assertTrue(inserts[0][3])
        self.assertEqual(list(writer.bulk_dir.glob("*.csv")), [])

    def test_auto_does_not_hide_data_validation_error(self):
        error = pyodbc.OperationalError("42000", "Invalid prepared survey. (51031)")
        connection = FakeConnection(bulk_error=error)
        with self.assertRaises(PersistenceError):
            self._writer(connection).write_set_based(
                BATCH_ID, [SURVEY], [], [], survey_mode="auto"
            )
        self.assertFalse(any(event[0] == "executemany" for event in connection.events))
        self.assertFalse(any(event[0] == "commit" for event in connection.events))


if __name__ == "__main__":
    unittest.main()
