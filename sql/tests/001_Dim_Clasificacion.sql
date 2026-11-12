-- Prueba de un registro de staging; todos los cambios se revierten.
USE [OpinionesDW];
GO
SET XACT_ABORT ON;
DECLARE @LotePrueba uniqueidentifier = NEWID();
DECLARE @Clase int;

BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.Stg_Opinion (
        IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    )
    SELECT TOP (1)
        @LotePrueba, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    FROM dbo.Stg_Opinion
    ORDER BY IdOpinion;
    IF @@ROWCOUNT <> 1
        THROW 51111, 'No hay una opinion preparada para la prueba.', 1;

    SELECT @Clase = IdClasificacion
    FROM dbo.Stg_Opinion WHERE IdEjecucion = @LotePrueba;

    EXEC dbo.usp_CargarDimClasificacion @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (
        SELECT 1 FROM dbo.Dim_Clasificacion
        WHERE IdClasificacion = @Clase
    )
        THROW 51112, 'La clasificacion del lote no quedo cubierta.', 1;

    EXEC dbo.usp_CargarDimClasificacion @IdEjecucion = @LotePrueba;

    ROLLBACK TRANSACTION;
    SELECT 'OK: una clave cubierta y segunda ejecucion sin duplicado' AS Resultado;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
