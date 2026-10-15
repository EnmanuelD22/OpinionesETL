"""Reglas declarativas para validar los lotes de entrada."""

#region Imports
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple
#endregion


#region Schema models
@dataclass(frozen=True)
class FieldRule:
    """Regla de validación para una columna del modelo transaccional."""

    name: str
    field_type: str
    required: bool = True
    max_length: Optional[int] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None


@dataclass(frozen=True)
class DataSchema:
    """Esquema mínimo que debe cumplir un lote antes de persistirse."""

    rules: Tuple[FieldRule, ...]

    @classmethod
    def from_rules(cls, rules: Iterable[FieldRule]) -> "DataSchema":
        return cls(tuple(rules))

    @property
    def required_columns(self) -> list[str]:
        return [rule.name for rule in self.rules if rule.required]
#endregion
