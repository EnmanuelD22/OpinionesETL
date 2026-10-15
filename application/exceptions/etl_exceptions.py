"""Excepciones del contrato ETL."""


class ETLError(RuntimeError):
    """Error base para que la aplicación pueda reportar fallas ETL."""


class ExtractionError(ETLError):
    """No fue posible leer la fuente de datos."""


class TransformationError(ETLError):
    """La transformación no pudo producir un lote válido."""


class PersistenceError(ETLError):
    """El adaptador no pudo persistir el lote."""


class CatalogError(ETLError):
    """No fue posible preparar o consultar los catálogos."""
