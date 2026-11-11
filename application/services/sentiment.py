"""Línea base local y reproducible de sentimiento en español.

El resultado es una predicción; las etiquetas de origen nunca se sobrescriben.
"""

import re
import unicodedata
from dataclasses import dataclass

VERSION = "lexico-es-v1"
POSITIVAS = {"bueno", "buena", "excelente", "perfecto", "perfecta", "recomendable",
             "recomiendo", "rapido", "rapida", "gran", "funciona", "encanta",
             "satisfecho", "satisfecha", "cumplio", "resolvio"}
NEGATIVAS = {"malo", "mala", "pesimo", "pesima", "deficiente", "roto", "rota",
             "rompio", "lento", "lenta", "decepcion", "decepcionado",
             "decepcionada", "problema", "fallo", "terrible", "danado", "danada",
             "dejo"}


@dataclass(frozen=True)
class Prediccion:
    id_clasificacion: int
    confianza: float
    version: str = VERSION


def clasificar(comentario: str) -> Prediccion:
    """1 positiva, 2 negativa, 3 neutra; confianza 0 significa sin evidencia."""
    texto = unicodedata.normalize("NFKD", comentario.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    palabras = re.findall(r"[a-z]+", texto)
    if "no era lo que esperaba" in texto:
        return Prediccion(2, 1.0)
    puntaje = aciertos = 0
    for indice, palabra in enumerate(palabras):
        polaridad = (palabra in POSITIVAS) - (palabra in NEGATIVAS)
        if polaridad:
            if "no" in palabras[max(0, indice - 2):indice]:
                polaridad = -polaridad
            puntaje += polaridad
            aciertos += 1
    clase = 1 if puntaje > 0 else 2 if puntaje < 0 else 3
    return Prediccion(clase, round(abs(puntaje) / aciertos, 3) if aciertos else 0.0)
