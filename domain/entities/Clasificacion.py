"""Entidad de dominio para la clasificación de una opinión."""

#region Imports
from dataclasses import dataclass
#endregion


#region Entity
@dataclass
class Clasificacion:
    IdClasificacion: int
    Tipo: str
#endregion
