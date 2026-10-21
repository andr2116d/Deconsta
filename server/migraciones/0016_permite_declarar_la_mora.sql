-- La mora de una cuota vencida: la declara quien paga, con una prueba (un documento de la empresa
-- con el monto con mora o el voucher que ya la pagó), y la aprueba o rechaza el gerente. Mientras
-- espera su decisión, la cuota no se paga; aprobada, su pago puede incluirla.
--
-- La prueba se sube y se analiza como un comprobante, con otro propósito: nunca respalda un pago.
-- Solo se agregan columnas y una tabla: los datos existentes no cambian.

ALTER TABLE comprobante_pago
    ADD COLUMN proposito text NOT NULL DEFAULT 'pago',
    ADD CONSTRAINT ck_comprobante_pago_proposito CHECK (proposito IN ('pago', 'mora')),
    ADD CONSTRAINT ck_comprobante_pago_respalda_pago CHECK (pago_id IS NULL OR proposito = 'pago');

CREATE TABLE mora (
    id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    deuda_id uuid NOT NULL,
    cuota integer NOT NULL,
    declarada_por uuid NOT NULL,
    -- Soles (PEN): lo que la empresa cobra de más por el atraso.
    importe numeric(12, 2) NOT NULL,
    prueba_id uuid NOT NULL,
    nota text,
    estado text NOT NULL,
    -- De 0 a 95, como en los pagos: cuánto respalda la prueba la mora declarada.
    confianza smallint NOT NULL,
    comprobaciones jsonb NOT NULL DEFAULT '[]',
    declarada_en timestamptz NOT NULL DEFAULT now(),
    decidida_por uuid,
    decidida_en timestamptz,
    motivo_decision text,
    CONSTRAINT pk_mora PRIMARY KEY (id),
    CONSTRAINT fk_mora_gerente_id_usuario FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_mora_declarada_por_usuario FOREIGN KEY (declarada_por) REFERENCES usuario (id),
    CONSTRAINT fk_mora_decidida_por_usuario FOREIGN KEY (decidida_por) REFERENCES usuario (id),
    CONSTRAINT fk_mora_cuota_deuda
        FOREIGN KEY (deuda_id, cuota) REFERENCES cuota_deuda (deuda_id, numero),
    CONSTRAINT fk_mora_prueba_id_comprobante_pago
        FOREIGN KEY (prueba_id) REFERENCES comprobante_pago (id),
    -- Una prueba respalda una sola mora.
    CONSTRAINT uq_mora_prueba_id UNIQUE (prueba_id),
    CONSTRAINT ck_mora_importe CHECK (importe > 0 AND importe <= 9999999.99),
    CONSTRAINT ck_mora_nota CHECK (nota IS NULL OR char_length(nota) BETWEEN 1 AND 500),
    CONSTRAINT ck_mora_estado CHECK (estado IN ('por_aprobar', 'aprobada', 'rechazada')),
    CONSTRAINT ck_mora_confianza CHECK (confianza BETWEEN 0 AND 95),
    -- Rechazar siempre deja su motivo: quien la declaró lo ve.
    CONSTRAINT ck_mora_motivo_rechazo CHECK (
        estado <> 'rechazada' OR char_length(motivo_decision) BETWEEN 1 AND 500
    )
);

-- Una cuota tiene a lo más una mora que espera o que ya se aprobó.
CREATE UNIQUE INDEX uq_mora_cuota_vigente ON mora (deuda_id, cuota)
    WHERE estado IN ('por_aprobar', 'aprobada');
CREATE INDEX ix_mora_gerente_id_estado ON mora (gerente_id, estado, declarada_en DESC);

-- Lo pagado por la mora, dentro del importe del pago.
ALTER TABLE pago
    ADD COLUMN mora numeric(12, 2) NOT NULL DEFAULT 0,
    ADD CONSTRAINT ck_pago_mora CHECK (mora >= 0 AND mora < importe);
