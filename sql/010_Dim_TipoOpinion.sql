-- Paso 5.2: carga selectiva de Dim_TipoOpinion desde un lote validado.
-- Solo toma los tipos presentes en Stg_Opinion; conserva la fila -1 del DW.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarDimTipoOpinion
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51201, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidas int = 0;
    DECLARE @Actualizadas int = 0;
    DECLARE @Insertadas int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            LEFT JOIN OpinionesETL.dbo.TipoOpinion AS t WITH (HOLDLOCK)
              ON t.IdTipoOpinion = s.IdTipoOpinion
            WHERE s.IdEjecucion = @IdEjecucion
              AND (t.IdTipoOpinion IS NULL
                   OR NULLIF(LTRIM(RTRIM(t.Nombre)), '') IS NULL
                   OR DATALENGTH(LTRIM(RTRIM(t.Nombre))) > 50)
        )
            THROW 51202, 'El lote contiene un tipo sin catalogo o nombre valido.', 1;

        SELECT DISTINCT t.IdTipoOpinion,
               LTRIM(RTRIM(t.Nombre)) AS Nombre
        INTO #Tipos
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        JOIN OpinionesETL.dbo.TipoOpinion AS t WITH (HOLDLOCK)
          ON t.IdTipoOpinion = s.IdTipoOpinion
        WHERE s.IdEjecucion = @IdEjecucion;
        SELECT @Leidas = COUNT(*) FROM #Tipos;

        UPDATE d
           SET d.Nombre = t.Nombre
        FROM dbo.Dim_TipoOpinion AS d
        JOIN #Tipos AS t
          ON t.IdTipoOpinion = d.IdTipoOpinion
        WHERE CONVERT(varbinary(50), d.Nombre) <> CONVERT(varbinary(50), t.Nombre);
        SET @Actualizadas = @@ROWCOUNT;

        INSERT INTO dbo.Dim_TipoOpinion (IdTipoOpinion, Nombre)
        SELECT t.IdTipoOpinion, t.Nombre
        FROM #Tipos AS t
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Dim_TipoOpinion AS d WITH (UPDLOCK, HOLDLOCK)
            WHERE d.IdTipoOpinion = t.IdTipoOpinion
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
