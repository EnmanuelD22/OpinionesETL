-- Paso 5.5: carga selectiva de Dim_Fuente desde un lote validado.
-- IdFuente identifica una sola combinación Canal/TipoFuente en el DW.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarDimFuente
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51501, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidas int = 0;
    DECLARE @Actualizadas int = 0;
    DECLARE @Insertadas int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            LEFT JOIN OpinionesETL.dbo.Fuente_Datos AS f WITH (HOLDLOCK)
              ON f.IdFuente = s.IdFuente
            WHERE s.IdEjecucion = @IdEjecucion
              AND (f.IdFuente IS NULL
                   OR NULLIF(LTRIM(RTRIM(s.Canal)), '') IS NULL
                   OR NULLIF(LTRIM(RTRIM(f.TipoFuente)), '') IS NULL
                   OR DATALENGTH(LTRIM(RTRIM(s.Canal))) > 50
                   OR DATALENGTH(LTRIM(RTRIM(f.TipoFuente))) > 50)
        )
            THROW 51502, 'El lote contiene una fuente o canal sin catalogo o nombre valido.', 1;

        IF EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            WHERE s.IdEjecucion = @IdEjecucion
            GROUP BY s.IdFuente
            HAVING COUNT(DISTINCT CONVERT(varbinary(50), LTRIM(RTRIM(s.Canal)))) > 1
        )
            THROW 51503, 'Un IdFuente tiene varios canales en el lote.', 1;

        SELECT s.IdFuente,
               MIN(LTRIM(RTRIM(s.Canal))) AS Canal,
               MAX(LTRIM(RTRIM(f.TipoFuente))) AS TipoFuente
        INTO #Fuentes
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        JOIN OpinionesETL.dbo.Fuente_Datos AS f WITH (HOLDLOCK)
          ON f.IdFuente = s.IdFuente
        WHERE s.IdEjecucion = @IdEjecucion
        GROUP BY s.IdFuente;
        SELECT @Leidas = COUNT(*) FROM #Fuentes;

        IF EXISTS (
            SELECT 1
            FROM #Fuentes AS f
            JOIN dbo.Dim_Fuente AS d WITH (UPDLOCK, HOLDLOCK)
              ON d.IdFuente = f.IdFuente
            WHERE CONVERT(varbinary(50), d.Canal) <>
                  CONVERT(varbinary(50), f.Canal)
        )
            THROW 51504, 'El canal del lote contradice Dim_Fuente.', 1;

        UPDATE d
           SET d.TipoFuente = f.TipoFuente
        FROM dbo.Dim_Fuente AS d
        JOIN #Fuentes AS f ON f.IdFuente = d.IdFuente
        WHERE CONVERT(varbinary(50), d.TipoFuente) <>
              CONVERT(varbinary(50), f.TipoFuente);
        SET @Actualizadas = @@ROWCOUNT;

        INSERT INTO dbo.Dim_Fuente (IdFuente, Canal, TipoFuente)
        SELECT f.IdFuente, f.Canal, f.TipoFuente
        FROM #Fuentes AS f
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Dim_Fuente AS d WITH (UPDLOCK, HOLDLOCK)
            WHERE d.IdFuente = f.IdFuente
        );
        SET @Insertadas = @@ROWCOUNT;

        -- Repetir la comprobación después del INSERT cubre carreras entre
        -- ejecuciones concurrentes que intenten asignar otro canal al ID.
        IF EXISTS (
            SELECT 1
            FROM #Fuentes AS f
            JOIN dbo.Dim_Fuente AS d WITH (UPDLOCK, HOLDLOCK)
              ON d.IdFuente = f.IdFuente
            WHERE CONVERT(varbinary(50), d.Canal) <>
                  CONVERT(varbinary(50), f.Canal)
        )
            THROW 51504, 'El canal del lote contradice Dim_Fuente.', 1;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;

    SELECT @Leidas AS ClavesLote,
           @Insertadas AS Insertadas,
           @Actualizadas AS Actualizadas;
END;
GO
