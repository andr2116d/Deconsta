-- Notificaciones de cada cuenta. Se guardan en la misma transacción que el evento que las origina,
-- así que siguen ahí aunque la persona cierre sesión o recargue la página; el aviso en tiempo real
-- solo anuncia que hay una nueva. La clave del evento impide notificar dos veces lo mismo.

CREATE TABLE notificacion (
    id uuid NOT NULL,
    destinatario_id uuid NOT NULL,
    tipo text NOT NULL,
    -- Evento que la origina, por ejemplo «deuda:<id>:registro».
    clave_evento text NOT NULL,
    titulo text NOT NULL,
    cuerpo text NOT NULL,
    deuda_id uuid,
    -- Cuenta a la que se refiere (la asistente bloqueada, por ejemplo).
    cuenta_id uuid,
    creada_en timestamptz NOT NULL DEFAULT now(),
    leida_en timestamptz,
    CONSTRAINT pk_notificacion PRIMARY KEY (id),
    CONSTRAINT fk_notificacion_destinatario_id_usuario
        FOREIGN KEY (destinatario_id) REFERENCES usuario (id),
    CONSTRAINT fk_notificacion_deuda_id_deuda FOREIGN KEY (deuda_id) REFERENCES deuda (id),
    CONSTRAINT fk_notificacion_cuenta_id_usuario FOREIGN KEY (cuenta_id) REFERENCES usuario (id),
    CONSTRAINT uq_notificacion_destinatario_evento UNIQUE (destinatario_id, clave_evento),
    CONSTRAINT ck_notificacion_tipo CHECK (tipo ~ '^[A-Z_]+$'),
    CONSTRAINT ck_notificacion_titulo CHECK (char_length(titulo) BETWEEN 1 AND 120),
    CONSTRAINT ck_notificacion_cuerpo CHECK (char_length(cuerpo) BETWEEN 1 AND 400)
);

CREATE INDEX ix_notificacion_destinatario_id_creada_en
    ON notificacion (destinatario_id, creada_en DESC);
CREATE INDEX ix_notificacion_no_leidas
    ON notificacion (destinatario_id) WHERE leida_en IS NULL;
