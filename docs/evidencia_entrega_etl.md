# Evidencia de la entrega ETL

## Fuentes y alcance

| Fuente analítica | Origen de lectura | Filas preparadas del lote comprobado |
|---|---|---:|
| Encuestas internas | `data/surveys_part1.csv`; base relacional solo para catálogos e identidad | 6 |
| Reseñas publicadas | `OpinionesETL.Opinion`, tipo 2 | 200 |
| Comentarios sociales | API paginada del proyecto, tipo 3 | 112 |

El CSV tiene 500 encuestas. Las otras 494 carecen de cliente o producto existente y quedan en `OpinionesDW.dbo.Stg_Rechazo` con motivo; no entran en `Fact_Opinion`. Los recuentos son de la instancia local de desarrollo, no constantes del programa. El lote de referencia usa `IdEjecucion = 31a8d32b-f73b-46b7-bb18-9b16f103bf7a`.

## Comprobaciones observadas en SQL Server

Las seis dimensiones se ejecutaron dos veces con el lote de referencia. Cubrieron sus claves y devolvieron cero inserciones y actualizaciones porque esos miembros ya existían. `sql/tests/001_Dim_Clasificacion.sql` a `005_Dim_Fecha.sql` cubren inserción y repetición dentro de transacciones revertidas; el tipo de opinión se comprobó con el lote real y su repetición.

`sql/tests/006_Fact_Opinion.sql` insertó una opinión sintética, comprobó que una segunda ejecución devolviera una fila sin cambios y terminó con `ROLLBACK`. La ejecución posterior del lote de referencia devolvió:

| Leídos | Insertados | Actualizados | Sin cambios | Total FACT |
|---:|---:|---:|---:|---:|
| 318 | 0 | 0 | 318 | 318 |

La orquestación Python se comprobó con `--load-existing-batch` autenticada como
`opiniones_etl_writer`: staging tenía 318 filas; las dimensiones cubrieron
respectivamente 3 clasificaciones, 3 tipos, 46 clientes, 26 productos,
3 fuentes y 191 fechas, todas con cero inserciones y actualizaciones. La FACT
devolvió 318 sin cambios. La carga de procedimientos tardó 0,5847 segundos.

`tools/create_sql_users.py` creó `opiniones_etl_writer` y `opiniones_dw_reader`, comprobó sus permisos mediante conexiones autenticadas como cada cuenta y, en una segunda ejecución, reconoció ambas cuentas existentes. El lector solo puede consultar dimensiones, FACT y vistas del DW. Las contraseñas están en `%LOCALAPPDATA%\OpinionesETL\sql_users.env`, fuera de Git.

## Verificación reproducible

1. Iniciar la API local y ejecutar `python -m tools.prepare_analytic_staging --load`. Guardar el `IdEjecucion` y revisar los contadores de las seis dimensiones y la FACT.
2. Para un lote ya preparado, ejecutar `python -m tools.prepare_analytic_staging --load-existing-batch ID-DEL-LOTE`, sin volver a extraer las fuentes.
3. Repetir el lote y confirmar que `Insertadas`/`Insertados` y `Actualizadas`/`Actualizados` sean cero si los catálogos y las opiniones no cambiaron.
4. Ejecutar `python -m unittest discover -s tests -v`. Esta comprobación debe finalizar por completo antes de considerar aprobada la suite.

La ejecución completa con `--load --survey-mode batch`, autenticada como
`opiniones_etl_writer`, pasó con un lote nuevo
`aa1e1589-295e-4174-8357-fbbbe3d9a081`: 500 encuestas leídas (6 preparadas,
494 rechazadas), 112 comentarios de API y 200 reseñas preparadas. Staging
contuvo 318 opiniones. Las seis dimensiones devolvieron 0 inserciones y 0
actualizaciones; la FACT devolvió 318 leídos y 318 sin cambios. Una segunda
carga de ese mismo lote con `--load-existing-batch` devolvió los mismos
recuentos, sin duplicar hechos. La suite Python pasó fuera del aislamiento
de sockets de Windows: `Ran 42 tests`, `OK`. Dentro de ese aislamiento la
prueba HTTP local se bloquea al crear el socket interno de `TestClient`.

## Auditoría de volumen: 50 000 comentarios sintéticos

`python -m tools.benchmark_50k_api` simuló 50 000 respuestas sociales paginadas:
500 páginas, 50 000 identificadores únicos y ordenados, 6,586 segundos y
51,03 MiB de memoria pico medida con `tracemalloc`. Esta prueba no insertó
filas en la base relacional.

`python -m tools.benchmark_50k_social` preparó 50 000 comentarios mediante TVP
en 50 lotes de 1000, llamó a las seis dimensiones y a la FACT, y repitió la
FACT en cada lote. La primera carga insertó 1000 por lote; la segunda devolvió
1000 sin cambios por lote. TVP tardó 13,022 segundos; el tramo SQL completo,
51,371 segundos. La transacción se revirtió: staging permaneció en 954 filas
y FACT en 318. La prueba inicial de un solo lote de 50 000 encontró espera
`RESOURCE_SEMAPHORE`; se limitó la concesión de memoria en el `INSERT` de la
FACT y se usaron lotes acotados. Las dos mediciones son de tramos separados;
no certifican por sí solas 50 000 registros reales de API a DW en una sola
ejecución.

## Comparación con el PDF de la actividad

El PDF pide arquitectura con servicio ETL, CSV, base relacional, API REST, DW
y dashboard; los diagramas y el código cubren esos componentes. Pide staging,
logs y una explicación de rendimiento, escalabilidad, seguridad y
mantenibilidad; están descritos en el diseño y ejercitados en estas pruebas.
También pide entregar un documento técnico en Word o PDF y publicar el código
en GitHub. Los documentos actuales están en Markdown y esta auditoría no
verificó una publicación en GitHub. El PDF dice .NET 8; el usuario confirmó
que el maestro autorizó Python para este proyecto.
