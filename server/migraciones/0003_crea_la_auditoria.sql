-- Historial de acciones importantes. Solo admite inserciones: los triggers rechazan cualquier
-- UPDATE, DELETE o TRUNCATE para que el historial no pueda modificarse desde la aplicación.

CREATE TABLE auditoria (
    id bigint GENERATED ALWAYS AS IDENTITY,
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    accion text NOT NULL,
    -- Quién realizó la acción; nulo cuando no hay una cuenta identificada.
    actor_id uuid,
    -- Cuenta afectada por la acción.
    cuenta_id uuid,
    motivo text,
    detalle jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT pk_auditoria PRIMARY KEY (id),
    CONSTRAINT fk_auditoria_actor_id_usuario FOREIGN KEY (actor_id) REFERENCES usuario (id),
    CONSTRAINT fk_auditoria_cuenta_id_usuario FOREIGN KEY (cuenta_id) REFERENCES usuario (id),
    CONSTRAINT ck_auditoria_accion CHECK (accion ~ '^[A-Z_]+$'),
    CONSTRAINT ck_auditoria_motivo CHECK (char_length(motivo) <= 500)
);

CREATE INDEX ix_auditoria_cuenta_id_ocurrido_en ON auditoria (cuenta_id, ocurrido_en DESC);

CREATE FUNCTION impedir_cambios_auditoria() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La auditoría no admite %', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER tg_auditoria_inmutable
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION impedir_cambios_auditoria();

CREATE TRIGGER tg_auditoria_sin_truncate
    BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION impedir_cambios_auditoria();
