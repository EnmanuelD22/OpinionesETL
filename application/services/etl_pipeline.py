"""Casos de uso para coordinar la ejecución del ETL.

Este módulo pertenece a aplicación y solo depende de puertos. Las fábricas de
CSV, SQLAlchemy y cualquier otra tecnología se inyectan desde `main.py`.
"""

#region Imports
from typing import Callable, Iterable, Mapping

from application.interfaces.services.ICatalogService import ICatalogService
from application.interfaces.services.IExtractor import IExtractor
from application.interfaces.services.ILoader import ILoader
from application.interfaces.services.ITransformer import ITransformer
from application.models.etl_results import ETLResult, PipelineResult
#endregion


#region Pipeline
class ETLPipeline:
    """Ejecuta un ciclo aislado de extracción, transformación y carga."""

    #region Construction
    def __init__(
        self,
        nombre_proceso: str,
        extractor: IExtractor,
        transformer: ITransformer,
        loader: ILoader,
    ):
        self.nombre_proceso = nombre_proceso
        self.extractor = extractor
        self.transformer = transformer
        self.loader = loader
        self.last_result: PipelineResult | None = None
    #endregion

    #region Execution
    def ejecutar(self) -> dict[str, int]:
        """Ejecuta el pipeline y mantiene la salida histórica en español."""

        print(f"\n{'=' * 50}\nEjecutando ETL: {self.nombre_proceso}\n{'=' * 50}")
        datos = self.extractor.extract()
        listos, rechazados_transformacion = self.transformer.transformar(datos)
        insertados, rechazados_carga = self.loader.cargar(listos)
        resultado = PipelineResult(
            processed=len(datos),
            inserted=insertados,
            rejected=rechazados_transformacion + rechazados_carga,
            rejection_reasons={
                **getattr(self.transformer, "last_rejection_reasons", {}),
                **({"duplicado_en_base": rechazados_carga} if rechazados_carga else {}),
            },
        )
        self.last_result = resultado
        print(
            f"Procesados: {resultado.processed} | "
            f"Insertados: {resultado.inserted} | "
            f"Rechazados: {resultado.rejected}"
        )
        return {
            "procesados": resultado.processed,
            "insertados": resultado.inserted,
            "rechazados": resultado.rejected,
        }
    #endregion
#endregion


#region Application use case
class ETLApplication:
    """Caso de uso que coordina maestros y opiniones en orden de dependencia."""

    def __init__(
        self,
        catalog_service: ICatalogService,
        pipelines_base: Iterable[ETLPipeline],
        pipeline_product_factory: Callable[[Mapping[str, int]], ETLPipeline],
        pipelines_opiniones_factory: Callable[[Mapping[str, set[int]]], Iterable[ETLPipeline]],
    ):
        self.catalog_service = catalog_service
        self.pipelines_base = tuple(pipelines_base)
        self.pipeline_product_factory = pipeline_product_factory
        self.pipelines_opiniones_factory = pipelines_opiniones_factory

    #region Execution
    def ejecutar(self) -> dict[str, int]:
        """Prepara catálogos y ejecuta todos los lotes en orden."""

        contexto = self.catalog_service.preparar()
        acumulado = ETLResult()

        for pipeline in self.pipelines_base:
            acumulado = acumulado.add(self._resultado(pipeline))

        acumulado = acumulado.add(
            self._resultado(self.pipeline_product_factory(contexto.category_map))
        )

        referencias = self.catalog_service.obtener_referencias().references
        for pipeline in self.pipelines_opiniones_factory(referencias):
            acumulado = acumulado.add(self._resultado(pipeline))

        resultado = acumulado.as_dict()
        print("\nResumen del proceso ETL")
        print(
            f"Procesados: {resultado['procesados']} | "
            f"Insertados: {resultado['insertados']} | "
            f"Rechazados: {resultado['rechazados']}"
        )
        if acumulado.rejection_reasons:
            motivos = ", ".join(
                f"{motivo}: {cantidad}"
                for motivo, cantidad in sorted(acumulado.rejection_reasons.items())
            )
            print(f"Motivos de rechazo: {motivos}")
        return resultado

    @staticmethod
    def _resultado(pipeline: ETLPipeline) -> PipelineResult:
        pipeline.ejecutar()
        if pipeline.last_result is None:
            raise RuntimeError("El pipeline no produjo un resultado")
        return pipeline.last_result
    #endregion
#endregion


#region Compatibility entry point
def ejecutar_etl(application: ETLApplication) -> dict[str, int]:
    """Ejecuta una instancia configurada del caso de uso.

    La dependencia explícita evita que esta capa construya conexiones o
    adaptadores concretos por su cuenta.
    """

    return application.ejecutar()
#endregion
