-- Lotes sociales procedentes de la API, ya normalizados y validados en Python.
-- pyodbc codifica NULL opcionales como 0 en el TVP; el procedimiento los restaura.
-- Requiere sql/004_Staging.sql. No modifica dimensiones ni Fact_Opinion.
USE [OpinionesDW];
GO

IF TYPE_ID(N'dbo.TVP_OpinionSocial') IS NULL
    EXEC(N'
        CREATE TYPE dbo.TVP_OpinionSocial AS TABLE (
            IdOrigen varchar(50) NOT NULL PRIMARY KEY,
            IdOpinion int NOT NULL UNIQUE,
            IdCliente int NOT NULL,
            IdProducto int NOT NULL,
            Fecha date NOT NULL,
            Comentario varchar(max) NOT NULL,
            IdFuente int NOT NULL,
            Canal varchar(50) NOT NULL,
            Puntaje decimal(3,1) NULL,
            IdClasificacionOriginal int NULL,
            IdClasificacionPredicha int NULL,
            IdClasificacion int NOT NULL
        )');
GO

CREATE OR ALTER PROCEDURE dbo.usp_StagingSocial_TVP
    @IdEjecucion uniqueidentifier,
    @Filas dbo.TVP_OpinionSocial READONLY
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51001, 'IdEjecucion es obligatorio.', 1;

    IF EXISTS (
        SELECT 1
        FROM @Filas AS f
        WHERE f.IdOpinion <= 0
           OR f.IdCliente <= 0
           OR f.IdProducto <= 0
           OR f.IdFuente <= 0
           OR NULLIF(LTRIM(RTRIM(f.IdOrigen)), '') IS NULL
           OR NULLIF(LTRIM(RTRIM(f.Comentario)), '') IS NULL
           OR NULLIF(LTRIM(RTRIM(f.Canal)), '') IS NULL
           OR (f.Puntaje IS NOT NULL AND f.Puntaje <> 0
               AND (f.Puntaje < 1 OR f.Puntaje > 5))
           OR (f.IdClasificacionOriginal IS NOT NULL
               AND f.IdClasificacionOriginal NOT IN (0, 1, 2, 3))
           OR (f.IdClasificacionPredicha IS NOT NULL
               AND f.IdClasificacionPredicha NOT IN (0, 1, 2, 3))
           OR f.IdClasificacion NOT IN (1, 2, 3)
           OR COALESCE(NULLIF(f.IdClasificacionOriginal, 0),
                       NULLIF(f.IdClasificacionPredicha, 0)) IS NULL
           OR f.IdClasificacion <> COALESCE(NULLIF(f.IdClasificacionOriginal, 0),
                                           NULLIF(f.IdClasificacionPredicha, 0))
    )
        THROW 51002, 'El TVP social contiene filas invalidas.', 1;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Una clave IdOpinion no puede representar otro origen dentro del lote.
        IF EXISTS (
            SELECT 1
            FROM @Filas AS f
            JOIN dbo.Stg_Opinion AS s WITH (UPDLOCK, HOLDLOCK)
              ON s.IdEjecucion = @IdEjecucion
             AND s.IdOpinion = f.IdOpinion
            WHERE s.IdTipoOpinion <> 3 OR s.IdOrigen <> f.IdOrigen
        )
            THROW 51003, 'IdOpinion ya pertenece a otro origen del lote.', 1;

        IF EXISTS (
            SELECT 1
            FROM @Filas AS f
            JOIN dbo.Stg_Opinion AS s WITH (UPDLOCK, HOLDLOCK)
              ON s.IdEjecucion = @IdEjecucion
             AND s.IdTipoOpinion = 3
             AND s.IdOrigen = f.IdOrigen
            WHERE s.IdOpinion <> f.IdOpinion
        )
            THROW 51004, 'IdOrigen social ya tiene otro IdOpinion en el lote.', 1;

        UPDATE s
           SET s.IdCliente = f.IdCliente,
               s.IdProducto = f.IdProducto,
               s.Fecha = f.Fecha,
               s.Comentario = f.Comentario,
               s.IdFuente = f.IdFuente,
               s.Canal = f.Canal,
               s.Puntaje = NULLIF(f.Puntaje, 0),
               s.IdClasificacionOriginal = NULLIF(f.IdClasificacionOriginal, 0),
               s.IdClasificacionPredicha = NULLIF(f.IdClasificacionPredicha, 0),
               s.IdClasificacion = f.IdClasificacion,
               s.Estado = 'VALIDADO'
        FROM dbo.Stg_Opinion AS s
        JOIN @Filas AS f ON f.IdOrigen = s.IdOrigen
        WHERE s.IdEjecucion = @IdEjecucion
          AND s.IdTipoOpinion = 3;

        INSERT INTO dbo.Stg_Opinion (
            IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
            IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
            IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
        )
        SELECT @IdEjecucion, 3, f.IdOrigen, f.IdOpinion, f.IdCliente,
               f.IdProducto, f.Fecha, f.Comentario, f.IdFuente, f.Canal,
               NULLIF(f.Puntaje, 0), NULLIF(f.IdClasificacionOriginal, 0),
               NULLIF(f.IdClasificacionPredicha, 0), f.IdClasificacion
        FROM @Filas AS f
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (UPDLOCK, HOLDLOCK)
            WHERE s.IdEjecucion = @IdEjecucion
              AND s.IdTipoOpinion = 3
              AND s.IdOrigen = f.IdOrigen
        );

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO
