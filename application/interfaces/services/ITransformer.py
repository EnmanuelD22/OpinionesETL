"""Puerto para transformar y validar lotes."""

#region Imports
from abc import ABC, abstractmethod
from typing import Tuple

import pandas as pd
#endregion


#region Port
class ITransformer(ABC):
    """Contrato de transformación usado por el caso de uso."""

    @abstractmethod
    def transformar(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Devuelve el lote válido y la cantidad rechazada."""

        raise NotImplementedError
#endregion
