"""Puerto de salida para persistir lotes tabulares."""

#region Imports
from abc import ABC, abstractmethod
from typing import Tuple

import pandas as pd
#endregion


#region Port
class ILoader(ABC):
    """Contrato de carga independiente de SQL Server u otra tecnología."""

    @abstractmethod
    def cargar(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Devuelve `(insertados, rechazados)` para el lote recibido."""

        raise NotImplementedError
#endregion
