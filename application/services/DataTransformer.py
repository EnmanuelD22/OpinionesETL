"""Transformador de lotes del caso de uso ETL."""

#region Imports
from collections import Counter

import pandas as pd

from application.exceptions.etl_exceptions import TransformationError
from application.interfaces.services.ITransformer import ITransformer
from application.models.schema import DataSchema, FieldRule
#endregion


#region Transformer
class DataTransformer(ITransformer):
    """Normaliza, valida y documenta los rechazos de cada lote."""

    #region Construction
    def __init__(
        self,
        columnas_requeridas,
        clave_duplicados=None,
        renombrar=None,
        columnas_salida=None,
        mapas=None,
        valores_default=None,
        referencias=None,
        esquema: DataSchema | None = None,
    ):
        self.columnas_requeridas = list(columnas_requeridas)
        self.clave_duplicados = list(clave_duplicados or columnas_requeridas)
        self.renombrar = dict(renombrar or {})
        self.columnas_salida = list(columnas_salida) if columnas_salida else None
        self.mapas = dict(mapas or {})
        self.valores_default = dict(valores_default or {})
        self.referencias = dict(referencias or {})
        self.esquema = esquema or self._esquema_implicit()
        self.last_rejection_reasons: dict[str, int] = {}
    #endregion

    #region Transformation
    def transformar(self, datos):
        """Devuelve `(datos_validos, cantidad_rechazada)`.

        Los motivos del último lote quedan disponibles en
        `last_rejection_reasons`, sin romper el contrato histórico de tupla.
        Cada registro recibe un único motivo: el primer filtro que lo rechaza.
        """

        datos = datos.rename(columns=self.renombrar).copy()
        for columna, valor in self.valores_default.items():
            datos[columna] = valor

        faltantes = set(self.columnas_requeridas) - set(datos.columns)
        if faltantes:
            raise TransformationError(
                f"Faltan columnas obligatorias: {', '.join(sorted(faltantes))}"
            )

        total = len(datos)
        datos["_etl_row_id"] = range(total)
        motivos: dict[int, str] = {}

        duplicados = ~datos.duplicated(subset=self.clave_duplicados, keep="first")
        datos = self._conservar_validos(datos, duplicados, "registro_duplicado", motivos)

        for columna, valores in self.mapas.items():
            if columna in datos.columns:
                datos[columna] = datos[columna].map(valores)

        for columna in datos.columns:
            if columna in {"IdCliente", "IdProducto", "IdFuente", "IdCategoria", "IdClasificacion"}:
                valores_texto = datos[columna].astype("string").str.strip()
                valores_numericos = pd.to_numeric(valores_texto, errors="coerce")
                valores_codificados = valores_texto.str.extract(
                    r"^[A-Za-z]*(\d+)$", expand=False
                )
                datos[columna] = valores_numericos.where(
                    valores_numericos.notna(),
                    pd.to_numeric(valores_codificados, errors="coerce"),
                )

        for columna in ("IdCliente", "IdProducto", "IdFuente", "IdCategoria", "IdClasificacion"):
            if columna in self.columnas_requeridas:
                validos = datos[columna].notna()
                datos = self._conservar_validos(
                    datos, validos, "id_invalido_o_vacio", motivos
                )

        for columna, permitidos in self.referencias.items():
            if columna in datos.columns:
                validos = datos[columna].isin(permitidos)
                datos = self._conservar_validos(
                    datos, validos, "integridad_referencial", motivos
                )

        for columna in ("Nombre", "email", "TipoFuente", "Comentario"):
            if columna in datos.columns:
                datos[columna] = datos[columna].astype("string").str.strip()
        if "email" in datos.columns:
            datos["email"] = datos["email"].str.lower()

        for columna in ("Fecha", "FechaCarga"):
            if columna in datos.columns:
                datos[columna] = pd.to_datetime(
                    datos[columna], errors="coerce", format="mixed"
                ).dt.date
                validos = datos[columna].notna()
                datos = self._conservar_validos(
                    datos, validos, "fecha_invalida_o_vacia", motivos
                )

        if "Puntaje" in datos.columns:
            datos["Puntaje"] = pd.to_numeric(datos["Puntaje"], errors="coerce")
            regla_puntaje = next(
                (regla for regla in self.esquema.rules if regla.name == "Puntaje"),
                FieldRule("Puntaje", "number", minimum=1, maximum=5),
            )
            minimo = 1 if regla_puntaje.minimum is None else regla_puntaje.minimum
            maximo = 5 if regla_puntaje.maximum is None else regla_puntaje.maximum
            validos = datos["Puntaje"].between(minimo, maximo, inclusive="both")
            datos = self._conservar_validos(
                datos, validos, "puntaje_invalido", motivos
            )

        for regla in self.esquema.rules:
            if regla.name not in datos.columns or regla.max_length is None:
                continue
            validos = datos[regla.name].astype("string").str.len().le(regla.max_length)
            datos = self._conservar_validos(
                datos, validos, "longitud_excedida", motivos
            )

        if "email" in self.columnas_requeridas and "email" in datos.columns:
            validos = datos["email"].str.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+", na=False
            )
            datos = self._conservar_validos(
                datos, validos, "email_invalido", motivos
            )

        for columna in ("Nombre", "email", "TipoFuente", "Comentario"):
            if columna in self.columnas_requeridas and columna in datos.columns:
                validos = datos[columna].astype("string").str.strip().ne("")
                datos = self._conservar_validos(
                    datos, validos, "campo_obligatorio_vacio", motivos
                )

        campos_a_validar = [c for c in self.columnas_requeridas if c in datos.columns]
        if campos_a_validar:
            validos = datos[campos_a_validar].notna().all(axis=1)
            datos = self._conservar_validos(
                datos, validos, "campo_obligatorio_vacio", motivos
            )

        for columna in ("IdCliente", "IdProducto", "IdFuente", "IdCategoria", "IdClasificacion"):
            if columna in datos.columns and datos[columna].notna().all():
                datos[columna] = datos[columna].astype("int64")

        self.last_rejection_reasons = dict(Counter(motivos.values()))
        datos = datos.drop(columns=["_etl_row_id"])
        if self.columnas_salida:
            datos = datos[self.columnas_salida]

        return datos.reset_index(drop=True), total - len(datos)
    #endregion

    #region Validation helpers
    def _esquema_implicit(self) -> DataSchema:
        reglas = []
        for columna in self.columnas_requeridas:
            if columna.startswith("Id"):
                tipo = "integer"
            elif columna in {"Fecha", "FechaCarga"}:
                tipo = "date"
            elif columna == "Puntaje":
                tipo = "number"
            else:
                tipo = "text"
            reglas.append(FieldRule(columna, tipo, required=True))
        return DataSchema.from_rules(reglas)

    @staticmethod
    def _conservar_validos(datos, validos, motivo, motivos):
        validos = validos.fillna(False).astype(bool)
        for row_id in datos.loc[~validos, "_etl_row_id"].tolist():
            motivos.setdefault(row_id, motivo)
        return datos.loc[validos].copy()
    #endregion
#endregion
