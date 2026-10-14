from abc import ABC, abstractmethod
import pandas as pd
from typing import Tuple

class ITransformer(ABC): 
    @abstractmethod
    def transformar(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]: 
        pass