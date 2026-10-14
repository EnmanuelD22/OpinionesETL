
from abc import ABC, abstractmethod
import pandas as pd
from typing import Tuple

class ILoader(ABC):
    @abstractmethod
    def cargar(self, df: pd.DataFrame) -> Tuple[int, int]:
        pass