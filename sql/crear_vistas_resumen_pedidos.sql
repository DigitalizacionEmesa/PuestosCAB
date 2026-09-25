/* Preferencias personales de columnas y filtros del Resumen de Pedidos CAB. */
IF OBJECT_ID(N'CAB.ResumenPedidosVistas', N'U') IS NULL
BEGIN
    CREATE TABLE CAB.ResumenPedidosVistas (
        Usuario NVARCHAR(100) NOT NULL,
        Vistas NVARCHAR(MAX) NOT NULL CONSTRAINT DF_ResumenPedidosVistas_Vistas DEFAULT N'[]',
        VistaPredeterminada NVARCHAR(80) NULL,
        FechaActualizacion DATETIME2(0) NOT NULL CONSTRAINT DF_ResumenPedidosVistas_Fecha DEFAULT SYSDATETIME(),
        CONSTRAINT PK_ResumenPedidosVistas PRIMARY KEY (Usuario)
    );
END;

IF COL_LENGTH(N'CAB.ResumenPedidosVistas', N'VistaPredeterminada') IS NULL
BEGIN
    ALTER TABLE CAB.ResumenPedidosVistas
        ADD VistaPredeterminada NVARCHAR(80) NULL;
END;
