-- Intentos de una asistente de registrar un documento que ya respalda otra deuda, y el bloqueo de
-- su registro de deudas al tercero en 24 horas. El bloqueo no toca su cuenta: puede seguir
-- ingresando y trabajando; solo no registra deudas hasta que su gerente lo levante. Los intentos
-- solo admiten inserciones.

CREATE TABLE intento_documento_repetido (
    id bigint GENERATED ALWAYS AS IDENTITY,
    asistente_id uuid NOT NULL,
    -- Deuda que ya usa ese documento.
    deuda_id uuid NOT NULL,
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_intento_documento_repetido PRIMARY KEY (id),
    CONSTRAINT fk_intento_documento_repetido_asistente_id_usuario
        FOREIGN KEY (asistente_id) REFERENCES usuario (id),
    CONSTRAINT fk_intento_documento_repetido_deuda_id_deuda
        FOREIGN KEY (deuda_id) REFERENCES deuda (id)
);

CREATE INDEX ix_intento_documento_repetido_asistente_id
    ON intento_documento_repetido (asistente_id, ocurrido_en DESC);

CREATE TRIGGER tg_intento_documento_repetido_inmutable
    BEFORE UPDATE OR DELETE ON intento_documento_repetido
    FOR EACH ROW EXECUTE FUNCTION impedir_cambios_auditoria();

CREATE TABLE bloqueo_registro_deuda (
    id uuid NOT NULL,
    asistente_id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    bloqueado_en timestamptz NOT NULL DEFAULT now(),
    levantado_en timestamptz,
    levantado_por uuid,
    CONSTRAINT pk_bloqueo_registro_deuda PRIMARY KEY (id),
    CONSTRAINT fk_bloqueo_registro_deuda_asistente_id_usuario
        FOREIGN KEY (asistente_id) REFERENCES usuario (id),
    CONSTRAINT fk_bloqueo_registro_deuda_gerente_id_usuario
        FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_bloqueo_registro_deuda_levantado_por_usuario
        FOREIGN KEY (levantado_por) REFERENCES usuario (id),
    CONSTRAINT ck_bloqueo_registro_deuda_levantamiento
        CHECK ((levantado_en IS NULL) = (levantado_por IS NULL))
);

-- Una asistente tiene a lo más un bloqueo vigente.
CREATE UNIQUE INDEX uq_bloqueo_registro_deuda_vigente
    ON bloqueo_registro_deuda (asistente_id) WHERE levantado_en IS NULL;
