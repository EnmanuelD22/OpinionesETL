"""Resultados y contratos de salida del caso de uso ETL."""

#region Imports
from dataclasses import dataclass, field
from typing import Dict, Set
#endregion


#region Result models
@dataclass(frozen=True)
class LoadResult:
    """Resultado de persistir un lote de registros."""

    inserted: int
    rejected: int


@dataclass(frozen=True)
class PipelineResult:
    """Métricas de una ejecución de pipeline."""

    processed: int
    inserted: int
    rejected: int
    rejection_reasons: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ETLResult:
    """Métricas agregadas de toda la ejecución."""

    processed: int = 0
    inserted: int = 0
    rejected: int = 0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)

    def add(self, result: PipelineResult) -> "ETLResult":
        """Combina las métricas de un pipeline sin mutar el resultado."""

        return ETLResult(
            processed=self.processed + result.processed,
            inserted=self.inserted + result.inserted,
            rejected=self.rejected + result.rejected,
            rejection_reasons=self._merge_reasons(
                self.rejection_reasons, result.rejection_reasons
            ),
        )

    @staticmethod
    def _merge_reasons(*reason_maps: Dict[str, int]) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for reason_map in reason_maps:
            for reason, count in reason_map.items():
                merged[reason] = merged.get(reason, 0) + count
        return merged

    def as_dict(self) -> Dict[str, int]:
        """Representación compatible con la salida histórica del ETL."""

        return {
            "procesados": self.processed,
            "insertados": self.inserted,
            "rechazados": self.rejected,
        }


@dataclass(frozen=True)
class CatalogContext:
    """Referencias necesarias para validar las cargas posteriores."""

    category_map: Dict[str, int]
    references: Dict[str, Set[int]]
#endregion
