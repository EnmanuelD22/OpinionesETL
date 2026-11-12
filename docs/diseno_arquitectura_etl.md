# Diseño del ETL de opiniones

Base de referencia: scripts de `OpinionesETL` y `OpinionesDW` entregados el 11 de noviembre de 2026. Los diagramas de las bases describen el esquema existente; los de arquitectura y flujo describen la implementación objetivo. La API, el extractor HTTP, staging, las rutas de carga por conjuntos y los procedimientos de dimensiones y FACT están implementados. `main.py` conserva el proceso histórico; la preparación selectiva se ejecuta con `python -m tools.prepare_analytic_staging` y la opción `--load` añade la llamada ordenada a dimensiones y FACT.

## 1. Arquitectura propuesta

```mermaid
flowchart LR
    CSV[CSV de encuestas] --> CE[CsvExtractor]
    DB[(OpinionesETL)] --> RE[Extractor SQL de reseñas]
    DB --> API[API REST de comentarios sociales]
    API --> AE[ApiExtractor]
    CE --> VALID[Validación y normalización]
    RE --> VALID
    AE --> VALID
    VALID --> CLASS[Resolver clasificación]
    CLASS --> STG[(Staging por origen)]
    VALID --> RECH[(Rechazos con motivo)]
    CLASS --> RECH
    STG --> DIM[Procedimientos de dimensiones]
    DIM --> FACT[Procedimiento de Fact_Opinion]
    FACT --> DW[(OpinionesDW)]
    DW --> DASH[Dashboard y reportes]
    RUN[Ejecutor ETL Python] -. coordina .-> CE
    RUN -. coordina .-> RE
    RUN -. coordina .-> AE
    RUN -. registra .-> LOG[Logs y métricas]
```

La API lee opiniones sociales ya cargadas en `OpinionesETL`; no vuelve a insertarlas allí. El extractor SQL selecciona reseñas de la misma base. El CSV aporta los atributos de las encuestas. Los catálogos relacionales aportan los atributos de las dimensiones. La clasificación usa primero la etiqueta original y después la predicción existente; cuando faltan ambas se aplica el clasificador del proyecto solo a las filas seleccionadas.

## 2. Flujo de extracción y carga

```mermaid
flowchart TD
    A[Iniciar ejecución] --> B[Leer configuración y abrir registro de ejecución]
    B --> C{Fuente seleccionada}
    C -->|Encuestas| D[Leer CSV]
    C -->|Reseñas| E[Consultar base relacional]
    C -->|Sociales| F[Consumir API paginada]
    D --> G[Validar y normalizar]
    E --> G
    F --> G
    G --> H{Registro válido y no duplicado}
    H -->|No| I[Registrar rechazo y motivo]
    H -->|Sí| C1[Resolver clasificación e identidad]
    C1 -->|Sin clave o clase| I
    C1 -->|Completo| J[Enviar lote a staging]
    J --> K[Cargar dimensiones]
    K --> L[Cargar Fact_Opinion]
    L --> M[Comprobar conteos y referencias]
    I --> N[Registrar métricas finales]
    M --> N
```

## 3. Base relacional existente

```mermaid
erDiagram
    Categoria |o--o{ Producto : clasifica
    Cliente |o--o{ Opinion : escribe
    Producto |o--o{ Opinion : recibe
    Fuente_Datos |o--o{ Opinion : origina
    TipoOpinion |o--o{ Opinion : tipifica
    Clasificacion |o--o{ Opinion : etiqueta_original
    Opinion ||--o| AnalisisOpinion : tiene_prediccion
    Clasificacion ||--o{ AnalisisOpinion : etiqueta_predicha

    Categoria {
        int IdCategoria PK
        varchar Nombre
    }
    Cliente {
        int IdCliente PK
        varchar Nombre
        varchar email
    }
    Producto {
        int IdProducto PK
        varchar Nombre
        int IdCategoria FK
    }
    Fuente_Datos {
        int IdFuente PK
        varchar TipoFuente
        date FechaCarga
    }
    TipoOpinion {
        int IdTipoOpinion PK
        varchar Nombre
    }
    Clasificacion {
        int IdClasificacion PK
        varchar Tipo
    }
    Opinion {
        int IdOpinion PK
        varchar IdOrigen
        varchar Canal
        date Fecha
        varchar Comentario
        float Puntaje
        int IdCliente FK
        int IdProducto FK
        int IdClasificacion FK
        int IdFuente FK
        int IdTipoOpinion FK
    }
    AnalisisOpinion {
        int IdOpinion PK, FK
        int IdClasificacion FK
        float Confianza
        varchar ModeloVersion
    }
```

Las referencias de `Opinion` son anulables en el script. La relación con `AnalisisOpinion` es de cero o una predicción por opinión. La clasificación original y la predicha se conservan por separado.

## 4. Base analítica existente

```mermaid
erDiagram
    Dim_Fecha ||--o{ Fact_Opinion : fecha
    Dim_Cliente ||--o{ Fact_Opinion : cliente
    Dim_Producto ||--o{ Fact_Opinion : producto
    Dim_Fuente ||--o{ Fact_Opinion : fuente
    Dim_Clasificacion ||--o{ Fact_Opinion : clasificacion
    Dim_TipoOpinion ||--o{ Fact_Opinion : tipo

    Fact_Opinion {
        int IdOpinion PK
        int IdFecha FK
        int IdCliente FK
        int IdProducto FK
        int IdFuente FK
        int IdClasificacion FK
        decimal Puntaje
        varchar Comentario
        int IdTipoOpinion FK
    }
    Dim_Fecha {
        int IdFecha PK
        date Fecha
        smallint Anio
        tinyint Trimestre
        tinyint Mes
        varchar NombreMes
        char AnioMes
        tinyint Dia
    }
    Dim_Cliente {
        int IdCliente PK
        varchar Nombre
        varchar Email
    }
    Dim_Producto {
        int IdProducto PK
        varchar Nombre
        varchar Categoria
    }
    Dim_Fuente {
        int IdFuente PK
        varchar Canal
        varchar TipoFuente
    }
    Dim_Clasificacion {
        int IdClasificacion PK
        varchar Tipo
    }
    Dim_TipoOpinion {
        int IdTipoOpinion PK
        varchar Nombre
    }
```

`Fact_Opinion` representa los tres tipos de opinión; el tipo distingue encuesta, reseña y comentario social. Las seis claves foráneas son obligatorias. `IdOpinion` es una clave primaria entera sin `IDENTITY` en el DW.

## 5. Contrato de extracción y preparación

Una fila aceptada representa una opinión. `IdTipoOpinion` y `IdOrigen` identifican su procedencia; `IdOpinion` es la clave entera que exige la FACT. La extracción social y relacional usa los valores ya guardados en `Opinion`. Para encuestas, los atributos de negocio salen del CSV y la base relacional solo aporta catálogos y la correspondencia de identidad.

| Campo normalizado | Encuesta: `surveys_part1.csv` | Reseña: SQL relacional | Social: API local |
|---|---|---|---|
| `IdTipoOpinion` | Constante `1` | `Opinion.IdTipoOpinion = 2` | `Opinion.IdTipoOpinion = 3` |
| `IdOrigen` | `IdOpinion` del CSV, como texto | `Opinion.IdOrigen` | `Opinion.IdOrigen` |
| `IdOpinion` para FACT | Buscar `Opinion.IdOpinion` por tipo `1` + `IdOrigen` | `Opinion.IdOpinion` | `Opinion.IdOpinion` |
| `IdCliente`, `IdProducto` | Columnas homónimas del CSV | Columnas de `Opinion` | Columnas de `Opinion` |
| `Fecha`, `Comentario` | Columnas homónimas del CSV | Columnas de `Opinion` | Columnas de `Opinion` |
| `IdFuente`, `Canal` | Constantes `2`, `Encuestas` del pipeline vigente | `Opinion.IdFuente`, `Opinion.Canal` | `Opinion.IdFuente`, `Opinion.Canal` |
| `Puntaje` | `PuntajeSatisfacción`, obligatorio | `Opinion.Puntaje`, obligatorio según el pipeline vigente | `Opinion.Puntaje`; puede ser nulo |
| Clasificación original | `Clasificación`: Positiva=`1`, Negativa=`2`, Neutra=`3` | `Opinion.IdClasificacion` | `Opinion.IdClasificacion` |
| Clasificación predicha | No aplica si la etiqueta CSV es válida | `AnalisisOpinion.IdClasificacion` | `AnalisisOpinion.IdClasificacion` |

El campo `Fuente` del CSV de encuestas no se carga actualmente: el pipeline asigna `IdFuente=2` y `Canal=Encuestas`. Los archivos `web_reviews.csv` y `social_comments.csv` son muestras históricas y no son fuentes del nuevo flujo analítico. La API social expone los campos relacionales necesarios y las dos clasificaciones, ordenados y paginados por `IdOpinion`; no expone nombres ni correos de clientes.

### Reglas comunes

1. **Clasificación efectiva:** usar la original si existe; en otro caso, la predicha. En este paso, una fila sin ambas queda registrada como rechazo `sin_clasificacion_valida`, pendiente de clasificación selectiva antes de cargar la FACT. La integración futura del clasificador procesará solo el lote seleccionado y conservará la predicción por separado en `AnalisisOpinion`. La FACT requiere una clase válida entre `1`, `2` y `3`.
2. **Identidad:** las seis encuestas válidas actuales tienen correspondencia por `(IdTipoOpinion=1, IdOrigen)` con un `IdOpinion` relacional y con la FACT existente. Una encuesta futura sin correspondencia queda pendiente con motivo `sin_id_opinion_relacional`; la estructura actual de la FACT no permite asignarle un entero seguro sin definir una nueva política de identidad.
3. **Integridad:** exigir fecha, texto, identificador de origen, cliente, producto, fuente, tipo y clasificación válidos. `Puntaje` es obligatorio para encuestas y reseñas; en comentarios sociales puede ser nulo. Si viene informado debe estar entre `1` y `5`. La validación aplica esta regla según el tipo de opinión. Rechazar o dejar pendiente una fila con referencias o atributos dimensionales faltantes, sin inventar clientes, productos ni miembros desconocidos.
4. **Dimensiones:** `Dim_Cliente` toma nombre y correo de `Cliente`; `Dim_Producto`, nombre y categoría de `Producto` y `Categoria`; `Dim_Fuente`, canal de la opinión y tipo de `Fuente_Datos`; `Dim_TipoOpinion` y `Dim_Clasificacion`, sus catálogos; `Dim_Fecha` deriva `IdFecha=AAAAMMDD` y los atributos calendario. El mismo `IdFuente` no puede asociarse a canales distintos en un lote ni entre cargas, porque es la única clave de `Dim_Fuente`.
5. **Staging y cargas por conjuntos:** `sql/004_Staging.sql` crea `Stg_Opinion` y `Stg_Rechazo` en `OpinionesDW`. Conservan `IdEjecucion`, origen, identificadores, campos normalizados, clasificaciones original, predicha y efectiva, y el motivo de cada rechazo. `sql/005_TVP_Social.sql` carga comentarios de API mediante TVP; `sql/006_Bulk_Encuestas.sql` recibe un CSV temporal de encuestas ya validadas; `sql/007_Reviews_Set.sql` selecciona reseñas tipo 2 mediante `INSERT … SELECT`. El modo automático intenta BULK y usa `pyodbc.fast_executemany` solo si SQL Server no puede abrir o leer el archivo. `sql/008_Rechazo_IdOrigen.sql` amplía el identificador de rechazos en instalaciones existentes. `sql/009_Dim_Clasificacion.sql` a `sql/014_Dim_Fecha.sql` cargan las seis dimensiones y `sql/015_Fact_Opinion.sql` carga los hechos por conjuntos.
6. **Idempotencia:** deduplicar por `(IdTipoOpinion, IdOrigen)` en la entrada y por `IdOpinion` al cargar la FACT. La carga repetida no debe crear hechos adicionales ni reclasificar registros ya analizados.

### Alcance observado

La validación de la instancia encontró `6` encuestas, `200` reseñas y `112` comentarios sociales en la base relacional y los mismos `318` hechos en el DW. El CSV contiene `500` encuestas; `494` carecen de cliente o producto válido respecto de los catálogos actuales y se registraron en `Stg_Rechazo`. Estos números son una línea base de comprobación, no constantes del programa.

## 6. Límites del diseño

- El esquema no tiene estado de publicación. El proyecto vigente trata todas las opiniones de tipo `2` como reseñas publicadas; el nuevo extractor seguirá esa regla.
- `sp_LimpiarBaseDatosETL` borra datos y no forma parte del flujo selectivo ni de sus pruebas ordinarias.
- Los procedimientos de dimensiones y FACT están instalados y probados en SQL Server con el lote selectivo. La orquestación Python usa `--load` al preparar o `--load-existing-batch` para un lote ya preparado. Las tres rutas de staging por conjuntos están implementadas y probadas por separado.
