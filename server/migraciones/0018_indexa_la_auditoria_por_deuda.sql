-- El historial arma la línea de tiempo de cada deuda (registro, decisiones, pagos, moras y
-- pedidos) desde la auditoría, y filtra por la actividad dentro de un rango de fechas. Los eventos
-- de una deuda llevan su id en el detalle.
CREATE INDEX ix_auditoria_deuda_id_ocurrido_en
    ON auditoria ((detalle ->> 'deuda_id'), ocurrido_en)
    WHERE detalle ? 'deuda_id';
