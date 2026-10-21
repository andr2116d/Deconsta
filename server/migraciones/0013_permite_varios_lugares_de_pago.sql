-- Una deuda se puede pagar en varios lugares: la luz, por ejemplo, en un agente, por Yape o por
-- banca por internet. El lugar de cada deuda existente pasa a ser el único de su lista y la
-- columna anterior se quita después de copiarlo: ningún dato se pierde.

ALTER TABLE deuda ADD COLUMN lugares_pago text[];

UPDATE deuda SET lugares_pago = ARRAY[lugar_pago];

ALTER TABLE deuda
    ALTER COLUMN lugares_pago SET NOT NULL,
    -- Al menos uno, todos de la lista. La aplicación los guarda sin repetir y en orden.
    ADD CONSTRAINT ck_deuda_lugares_pago CHECK (
        cardinality(lugares_pago) BETWEEN 1 AND 6
        AND lugares_pago <@ ARRAY[
            'ventanilla', 'agente', 'banca_digital', 'transferencia', 'billetera',
            'debito_automatico'
        ]::text[]
    ),
    DROP CONSTRAINT ck_deuda_lugar_pago,
    DROP COLUMN lugar_pago;
