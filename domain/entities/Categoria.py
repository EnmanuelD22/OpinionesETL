"""Entidad de dominio para una categoría."""

#region Imports
from dataclasses import dataclass
from typing import Optional
#endregion


#region Entity
@dataclass
class Categoria:
    Nombre: str
    IdCategoria: Optional[int] = None
#endregion
