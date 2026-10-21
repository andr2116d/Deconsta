-- Un documento puede no ser una deuda por pagar: el comprobante de un pago ya hecho (Yape, Plin,
-- una transferencia) o algo que no cobra nada (una cotización, un documento de identidad). Queda
-- en el estado no_es_deuda y no respalda una deuda. Se agregan además los comprobantes de pago y
-- los estados de cuenta de tarjeta como tipos de documento. Solo se amplían los valores
-- permitidos: los datos existentes no cambian.

ALTER TABLE documento_deuda
    DROP CONSTRAINT ck_documento_deuda_estado,
    ADD CONSTRAINT ck_documento_deuda_estado CHECK (
        estado IN (
            'analizando', 'listo', 'ilegible', 'repetido', 'rechazado', 'no_es_deuda', 'fallido'
        )
    ),
    DROP CONSTRAINT ck_documento_deuda_tipo_documento,
    ADD CONSTRAINT ck_documento_deuda_tipo_documento CHECK (
        tipo_documento IN (
            'recibo_servicio', 'boleta', 'factura', 'cronograma', 'estado_cuenta', 'papeleta',
            'tributo', 'comprobante_pago', 'otro'
        )
    );
