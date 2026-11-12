-- Amplía el identificador original de rechazos sin perder valores existentes.
-- Necesario para registrar filas que superan el límite de Stg_Opinion.IdOrigen.
USE [OpinionesDW];
GO

IF EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.Stg_Rechazo', N'U')
      AND name = N'IdOrigen'
      AND (max_length <> -1 OR TYPE_NAME(system_type_id) <> N'nvarchar')
)
    ALTER TABLE dbo.Stg_Rechazo ALTER COLUMN IdOrigen nvarchar(max) NULL;
GO
