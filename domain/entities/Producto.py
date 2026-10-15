"""Entidad de dominio para un producto."""

#region Imports
from dataclasses import dataclass
from typing import Optional
#endregion


#region Entity
@dataclass
class Producto:
    IdProducto: int
    Nombre: str
    IdCategoria: Optional[int] = None
#endregion
