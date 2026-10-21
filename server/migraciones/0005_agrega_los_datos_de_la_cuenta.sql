-- Datos de la cuenta que la persona consulta y actualiza desde «Mi cuenta».
-- El cargo se fija al crear la cuenta y la persona no lo edita. El nombre como figura en los
-- recibos es un dato personal (se guarda cifrado) y solo lo tiene el gerente, titular de las deudas.
-- Las cuentas existentes quedan con ambos valores vacíos: no se altera ningún dato previo.

ALTER TABLE usuario
    ADD COLUMN cargo text,
    ADD COLUMN nombre_recibos_cifrado bytea,
    ADD CONSTRAINT ck_usuario_cargo CHECK (cargo IS NULL OR char_length(cargo) BETWEEN 2 AND 80),
    ADD CONSTRAINT ck_usuario_nombre_recibos_gerente
        CHECK (nombre_recibos_cifrado IS NULL OR rol = 'gerente');

-- Cada cambio del nombre de usuario hecho por la propia cuenta. Sirve para limitar los cambios por
-- mes y, como la auditoría, solo admite inserciones.
CREATE TABLE cambio_nombre_usuario (
    id bigint GENERATED ALWAYS AS IDENTITY,
    usuario_id uuid NOT NULL,
    anterior text NOT NULL,
    nuevo text NOT NULL,
    cambiado_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_cambio_nombre_usuario PRIMARY KEY (id),
    CONSTRAINT fk_cambio_nombre_usuario_usuario_id_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    CONSTRAINT ck_cambio_nombre_usuario_distinto CHECK (anterior <> nuevo)
);

CREATE INDEX ix_cambio_nombre_usuario_usuario_id_cambiado_en
    ON cambio_nombre_usuario (usuario_id, cambiado_en DESC);

CREATE TRIGGER tg_cambio_nombre_usuario_inmutable
    BEFORE UPDATE OR DELETE ON cambio_nombre_usuario
    FOR EACH ROW EXECUTE FUNCTION impedir_cambios();

CREATE TRIGGER tg_cambio_nombre_usuario_sin_truncate
    BEFORE TRUNCATE ON cambio_nombre_usuario
    FOR EACH STATEMENT EXECUTE FUNCTION impedir_cambios();
