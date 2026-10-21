-- El gerente pide a una asistente que pague una cuota: le llega un aviso que reaparece mientras la
-- cuota siga por pagar. El pedido deja de molestar cuando la cuota tiene un pago vigente o cuando
-- el gerente lo retira; si el pago se devuelve, vuelve a estar pendiente.

CREATE TABLE pedido_pago (
    id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    deuda_id uuid NOT NULL,
    cuota integer NOT NULL,
    asistente_id uuid NOT NULL,
    nota text,
    pedido_en timestamptz NOT NULL DEFAULT now(),
    retirado_en timestamptz,
    retirado_por uuid,
    CONSTRAINT pk_pedido_pago PRIMARY KEY (id),
    CONSTRAINT fk_pedido_pago_gerente_id_usuario FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_pedido_pago_asistente_id_usuario
        FOREIGN KEY (asistente_id) REFERENCES usuario (id),
    CONSTRAINT fk_pedido_pago_retirado_por_usuario
        FOREIGN KEY (retirado_por) REFERENCES usuario (id),
    CONSTRAINT fk_pedido_pago_cuota_deuda
        FOREIGN KEY (deuda_id, cuota) REFERENCES cuota_deuda (deuda_id, numero),
    CONSTRAINT ck_pedido_pago_nota CHECK (nota IS NULL OR char_length(nota) BETWEEN 1 AND 500),
    CONSTRAINT ck_pedido_pago_retiro CHECK ((retirado_en IS NULL) = (retirado_por IS NULL))
);

-- Una cuota tiene a lo más un pedido sin retirar.
CREATE UNIQUE INDEX uq_pedido_pago_vigente ON pedido_pago (deuda_id, cuota)
    WHERE retirado_en IS NULL;
CREATE INDEX ix_pedido_pago_asistente_id ON pedido_pago (asistente_id)
    WHERE retirado_en IS NULL;
