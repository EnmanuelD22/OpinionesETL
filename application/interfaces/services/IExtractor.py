"""Puerto de entrada para extracción de datos."""

#region Imports
from abc import ABC, abstractmethod

import pandas as pd
#endregion


#region Port
class IExtractor(ABC):
    """Contrato que debe cumplir cualquier fuente de datos."""

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Extrae un lote tabular o lanza un error de extracción."""

        raise NotImplementedError
#endregion
