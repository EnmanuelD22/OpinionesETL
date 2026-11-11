# Módulo 3: integración del NLP en el ETL

El módulo 3 conecta el contrato de clasificación del módulo 2 con la carga
analítica vigente. `main.py` solicita el clasificador en el punto de composición
y lo inyecta en `sincronizar_warehouse`. La selección activa sigue siendo
`lexico-es-v1`, porque el candidato de reseñas obtuvo menor F1 macro en el
fixture académico y todavía no cuenta con validación independiente. No existe
un interruptor de entorno que lo active por accidente.

## Flujo y procedencia

1. Se leen las opiniones de `OpinionesETL` junto con su etiqueta original y la
   predicción ya guardada, si existe.
2. Solo se envían al clasificador los comentarios con ambas clases ausentes.
   El adaptador recibe los textos en orden y un tamaño de lote de 16.
3. Se comprueba que haya una predicción por texto, con clase `1`, `2` o `3`,
   confianza finita entre 0 y 1 y versión no vacía de hasta 50 caracteres.
   Un comentario vacío o una respuesta inválida detiene la operación antes de
   insertar nuevas predicciones.
4. Las predicciones válidas se insertan en `OpinionesETL.dbo.AnalisisOpinion`
   con `IdOpinion`, `IdClasificacion`, `Confianza` y `ModeloVersion`. La clase
   original de `Opinion` permanece intacta.
5. `Fact_Opinion` recibe la etiqueta original cuando existe; en otro caso usa
   la predicción persistida. Las seis dimensiones y el grano de una fila por
   opinión del modelo estrella se conservan.

Una segunda ejecución no vuelve a clasificar opiniones ya analizadas ni duplica
hechos. Tampoco cambia silenciosamente predicciones antiguas si se inyecta otro
clasificador. Cualquier reemplazo o reproceso de versiones requerirá una
decisión y una migración explícitas tras validar el nuevo modelo.

## Bases de datos y ejecución

No se requiere un script SQL nuevo para este módulo: se utilizan las columnas
existentes de `AnalisisOpinion` y la estructura actual de `Fact_Opinion`. La
tabla `AnalisisOpinion` debe existir mediante `sql/001_OpinionesETL.sql`, que ya
forma parte de la preparación de la base relacional. El ETL activo no necesita
`requirements-nlp.txt`; esas dependencias son solo para evaluar el candidato.

La selección del clasificador está en `infrastructure/composition.py`. El
comparador del módulo 2 permanece separado del proceso que escribe en las bases.
Los CSV entregados por el maestro siguen siendo fuentes de solo lectura.

## Verificación

```powershell
python -m unittest discover -s tests -v
```

Las pruebas de integración usan SQLite en memoria y cubren la prioridad de la
etiqueta original, la inserción de clase/confianza/versión, la reutilización de
predicciones existentes, la repetición sin duplicados y el rechazo de lotes
inválidos antes de escribir. La comparación del candidato puede repetirse con
`python -m tools.compare_nlp_models --offline` cuando sus pesos ya estén en la
caché local.

Esta verificación no sustituye una prueba de carga de 50.000 comentarios en
SQL Server ni la evaluación independiente de opiniones reales por canal. Esas
son condiciones previas a promover un modelo distinto del léxico.
