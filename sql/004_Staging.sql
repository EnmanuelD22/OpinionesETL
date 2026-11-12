-- Preparación selectiva para OpinionesDW. Ejecutar después de crear OpinionesDW.
-- La migración crea tablas vacías y puede ejecutarse nuevamente sin borrar datos.
USE [OpinionesDW];
GO

IF OBJECT_ID(N'dbo.Stg_Opinion', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Stg_Opinion (
        IdEjecucion uniqueidentifier NOT NULL,
        IdTipoOpinion int NOT NULL,
        IdOrigen varchar(50) NOT NULL,
        IdOpinion int NOT NULL,
        IdCliente int NOT NULL,
        IdProducto int NOT NULL,
        Fecha date NOT NULL,
        Comentario varchar(max) NOT NULL,
        IdFuente int NOT NULL,
        Canal varchar(50) NOT NULL,
        Puntaje decimal(3,1) NULL,
        IdClasificacionOriginal int NULL,
        IdClasificacionPredicha int NULL,
        IdClasificacion int NOT NULL,
        Estado varchar(20) NOT NULL
            CONSTRAINT DF_Stg_Opinion_Estado DEFAULT ('VALIDADO'),
        FechaRegistro datetime2(0) NOT NULL
            CONSTRAINT DF_Stg_Opinion_FechaRegistro DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_Stg_Opinion PRIMARY KEY (IdEjecucion, IdTipoOpinion, IdOrigen),
        CONSTRAINT UQ_Stg_Opinion_Ejecucion_IdOpinion UNIQUE (IdEjecucion, IdOpinion),
        CONSTRAINT CK_Stg_Opinion_Tipo CHECK (IdTipoOpinion IN (1, 2, 3)),
        CONSTRAINT CK_Stg_Opinion_IdOpinion CHECK (IdOpinion > 0),
        CONSTRAINT CK_Stg_Opinion_Clasificacion CHECK (IdClasificacion IN (1, 2, 3)),
        CONSTRAINT CK_Stg_Opinion_Puntaje CHECK
            (Puntaje IS NULL OR Puntaje BETWEEN 1 AND 5),
        CONSTRAINT CK_Stg_Opinion_PuntajeObligatorio CHECK
            (IdTipoOpinion = 3 OR Puntaje IS NOT NULL)
    );
END;
GO

IF OBJECT_ID(N'dbo.Stg_Rechazo', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Stg_Rechazo (
        IdRechazo bigint IDENTITY(1,1) NOT NULL,
        IdEjecucion uniqueidentifier NOT NULL,
        Origen varchar(20) NOT NULL,
        IdOrigen nvarchar(max) NULL,
        Motivo varchar(100) NOT NULL,
        Detalle varchar(500) NULL,
        FechaRegistro datetime2(0) NOT NULL
            CONSTRAINT DF_Stg_Rechazo_FechaRegistro DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_Stg_Rechazo PRIMARY KEY (IdRechazo),
        CONSTRAINT CK_Stg_Rechazo_Origen CHECK
            (Origen IN ('encuesta', 'resena', 'social'))
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Stg_Rechazo')
      AND name = N'IX_Stg_Rechazo_Ejecucion_Origen'
)
    CREATE INDEX IX_Stg_Rechazo_Ejecucion_Origen
        ON dbo.Stg_Rechazo(IdEjecucion, Origen);
GO
