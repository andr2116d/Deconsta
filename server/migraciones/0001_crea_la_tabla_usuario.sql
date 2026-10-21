-- Cuentas de gerentes y asistentes.
-- Los datos personales se guardan cifrados con AES-256-GCM desde la aplicación (columnas *_cifrado).
-- Las columnas *_huella guardan un HMAC-SHA256 del valor normalizado para exigir unicidad sin
-- descifrar. La contraseña solo existe como hash Argon2id.

CREATE FUNCTION fijar_actualizado_en() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.actualizado_en = now();
    RETURN NEW;
END;
$$;

CREATE TABLE usuario (
    id uuid NOT NULL,
    rol text NOT NULL,
    gerente_id uuid,
    nombre_usuario text NOT NULL,
    contrasena_hash text NOT NULL,
    nombres_cifrado bytea NOT NULL,
    apellidos_cifrado bytea NOT NULL,
    correo_cifrado bytea NOT NULL,
    correo_huella bytea NOT NULL,
    telefono_cifrado bytea,
    tipo_documento text NOT NULL,
    numero_documento_cifrado bytea NOT NULL,
    numero_documento_huella bytea NOT NULL,
    -- Indicadores de primer ingreso (ultimo_ingreso_en nulo) y de contraseña inicial pendiente.
    debe_cambiar_contrasena boolean NOT NULL DEFAULT true,
    contrasena_actualizada_en timestamptz NOT NULL DEFAULT now(),
    ultimo_ingreso_en timestamptz,
    intentos_fallidos integer NOT NULL DEFAULT 0,
    bloqueada_en timestamptz,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_usuario PRIMARY KEY (id),
    CONSTRAINT fk_usuario_gerente_id_usuario FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT uq_usuario_nombre_usuario UNIQUE (nombre_usuario),
    CONSTRAINT uq_usuario_correo_huella UNIQUE (correo_huella),
    CONSTRAINT uq_usuario_documento_huella UNIQUE (tipo_documento, numero_documento_huella),
    CONSTRAINT ck_usuario_rol CHECK (rol IN ('gerente', 'asistente')),
    -- Toda asistente pertenece a un gerente; un gerente no depende de nadie.
    CONSTRAINT ck_usuario_rol_gerente CHECK ((rol = 'gerente') = (gerente_id IS NULL)),
    -- El nombre de usuario se guarda normalizado en minúsculas.
    CONSTRAINT ck_usuario_nombre_usuario
        CHECK (nombre_usuario ~ '^[a-z0-9][a-z0-9._-]{1,38}[a-z0-9]$'),
    CONSTRAINT ck_usuario_tipo_documento CHECK (tipo_documento IN ('dni', 'ce')),
    CONSTRAINT ck_usuario_intentos_fallidos CHECK (intentos_fallidos >= 0),
    -- El bloqueo por intentos fallidos solo se aplica a las asistentes.
    CONSTRAINT ck_usuario_bloqueo_asistente CHECK (bloqueada_en IS NULL OR rol = 'asistente')
);

CREATE INDEX ix_usuario_gerente_id ON usuario (gerente_id);

CREATE TRIGGER tg_usuario_actualizado_en
    BEFORE UPDATE ON usuario
    FOR EACH ROW EXECUTE FUNCTION fijar_actualizado_en();
