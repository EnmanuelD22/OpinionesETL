-- Paso 5.3: carga selectiva de Dim_Cliente desde un lote validado.
-- Los atributos vienen de OpinionesETL.dbo.Cliente; staging aporta las claves.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarDimCliente
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51301, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidas int = 0;
    DECLARE @Actualizadas int = 0;
    DECLARE @Insertadas int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            LEFT JOIN OpinionesETL.dbo.Cliente AS c WITH (HOLDLOCK)
              ON c.IdCliente = s.IdCliente
            WHERE s.IdEjecucion = @IdEjecucion
              AND (c.IdCliente IS NULL
                   OR NULLIF(LTRIM(RTRIM(c.Nombre)), '') IS NULL
                   OR DATALENGTH(LTRIM(RTRIM(c.Nombre))) > 200
                   OR DATALENGTH(LTRIM(RTRIM(c.email))) > 200)
        )
            THROW 51302, 'El lote contiene un cliente sin catalogo o nombre valido.', 1;

        SELECT DISTINCT c.IdCliente,
               LTRIM(RTRIM(c.Nombre)) AS Nombre,
               NULLIF(LTRIM(RTRIM(c.email)), '') AS Email
        INTO #Clientes
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        JOIN OpinionesETL.dbo.Cliente AS c WITH (HOLDLOCK)
          ON c.IdCliente = s.IdCliente
        WHERE s.IdEjecucion = @IdEjecucion;
        SELECT @Leidas = COUNT(*) FROM #Clientes;

        UPDATE d
           SET d.Nombre = c.Nombre,
               d.Email = c.Email
        FROM dbo.Dim_Cliente AS d
        JOIN #Clientes AS c ON c.IdCliente = d.IdCliente
        WHERE CONVERT(varbinary(200), d.Nombre) <> CONVERT(varbinary(200), c.Nombre)
           OR (d.Email IS NULL AND c.Email IS NOT NULL)
           OR (d.Email IS NOT NULL AND c.Email IS NULL)
           OR (d.Email IS NOT NULL AND c.Email IS NOT NULL
               AND CONVERT(varbinary(200), d.Email) <> CONVERT(varbinary(200), c.Email));
        SET @Actualizadas = @@ROWCOUNT;

        INSERT INTO dbo.Dim_Cliente (IdCliente, Nombre, Email)
        SELECT c.IdCliente, c.Nombre, c.Email
        FROM #Clientes AS c
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Dim_Cliente AS d WITH (UPDLOCK, HOLDLOCK)
            WHERE d.IdCliente = c.IdCliente
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
