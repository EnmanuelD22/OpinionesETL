-- Paso 5.1: carga selectiva de Dim_Clasificacion desde un lote validado.
-- Solo toma claves presentes en Stg_Opinion; conserva la fila -1 del DW.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarDimClasificacion
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51101, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidas int = 0;
    DECLARE @Actualizadas int = 0;
    DECLARE @Insertadas int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            LEFT JOIN OpinionesETL.dbo.Clasificacion AS c WITH (HOLDLOCK)
              ON c.IdClasificacion = s.IdClasificacion
            WHERE s.IdEjecucion = @IdEjecucion
              AND (c.IdClasificacion IS NULL
                   OR NULLIF(LTRIM(RTRIM(c.Tipo)), '') IS NULL
                   OR DATALENGTH(LTRIM(RTRIM(c.Tipo))) > 30)
        )
            THROW 51102, 'El lote contiene una clasificacion sin catalogo o nombre valido.', 1;

        SELECT DISTINCT c.IdClasificacion,
               LTRIM(RTRIM(c.Tipo)) AS Tipo
        INTO #Clasificaciones
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        JOIN OpinionesETL.dbo.Clasificacion AS c WITH (HOLDLOCK)
          ON c.IdClasificacion = s.IdClasificacion
        WHERE s.IdEjecucion = @IdEjecucion;
        SELECT @Leidas = COUNT(*) FROM #Clasificaciones;

        UPDATE d
           SET d.Tipo = c.Tipo
        FROM dbo.Dim_Clasificacion AS d
        JOIN #Clasificaciones AS c
          ON c.IdClasificacion = d.IdClasificacion
        WHERE CONVERT(varbinary(30), d.Tipo) <> CONVERT(varbinary(30), c.Tipo);
        SET @Actualizadas = @@ROWCOUNT;

        INSERT INTO dbo.Dim_Clasificacion (IdClasificacion, Tipo)
        SELECT c.IdClasificacion, c.Tipo
        FROM #Clasificaciones AS c
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Dim_Clasificacion AS d WITH (UPDLOCK, HOLDLOCK)
            WHERE d.IdClasificacion = c.IdClasificacion
        );
        SET @Insertadas = @@ROWCOUNT;

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
