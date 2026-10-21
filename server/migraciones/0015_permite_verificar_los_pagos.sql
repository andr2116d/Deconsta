-- El gerente verifica los pagos de sus asistentes: los confirma o los devuelve con un motivo. Un
-- pago devuelto deja de contar para su cuota, que vuelve a estar por pagar; sus comprobantes siguen
-- vinculados a él y no respaldan otro pago. Solo se agregan columnas y un estado: los pagos
-- existentes no cambian.

ALTER TABLE pago
    ADD COLUMN decidido_por uuid,
    ADD COLUMN decidido_en timestamptz,
    ADD COLUMN motivo_decision text,
    ADD CONSTRAINT fk_pago_decidido_por_usuario
        FOREIGN KEY (decidido_por) REFERENCES usuario (id),
    DROP CONSTRAINT ck_pago_estado,
    ADD CONSTRAINT ck_pago_estado CHECK (estado IN ('por_verificar', 'confirmado', 'devuelto')),
    -- Devolver siempre deja su motivo: la asistente lo ve.
    ADD CONSTRAINT ck_pago_motivo_devolucion CHECK (
        estado <> 'devuelto' OR char_length(motivo_decision) BETWEEN 1 AND 500
    );
