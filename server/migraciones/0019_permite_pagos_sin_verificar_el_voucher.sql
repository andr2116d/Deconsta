-- El gerente puede registrar un pago aunque el sistema no haya aceptado su voucher (rechazado,
-- ilegible o fallido): el pago queda confirmado con confianza 0 y la verificación omitida. Un voucher
-- repetido o que aún se analiza sigue sin respaldar pagos. Los índices únicos de archivo y operación
-- siguen impidiendo que un voucher respalde dos pagos.
ALTER TABLE comprobante_pago DROP CONSTRAINT ck_comprobante_pago_pago_listo;
ALTER TABLE comprobante_pago ADD CONSTRAINT ck_comprobante_pago_pago_respaldo CHECK (
    pago_id IS NULL OR estado IN ('listo', 'rechazado', 'ilegible', 'fallido')
);
