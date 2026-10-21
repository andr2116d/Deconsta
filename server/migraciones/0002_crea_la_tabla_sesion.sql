-- Sesiones de acceso. El navegador guarda el token en una cookie HttpOnly; aquí solo queda su
-- huella SHA-256, de modo que una copia de la base no permite suplantar sesiones.

CREATE TABLE sesion (
    id uuid NOT NULL,
    usuario_id uuid NOT NULL,
    token_huella bytea NOT NULL,
    creada_en timestamptz NOT NULL DEFAULT now(),
    expira_en timestamptz NOT NULL,
    revocada_en timestamptz,
    motivo_revocacion text,
    CONSTRAINT pk_sesion PRIMARY KEY (id),
    CONSTRAINT fk_sesion_usuario_id_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id) ON DELETE CASCADE,
    CONSTRAINT uq_sesion_token_huella UNIQUE (token_huella),
    CONSTRAINT ck_sesion_expira_en CHECK (expira_en > creada_en),
    CONSTRAINT ck_sesion_revocacion CHECK ((revocada_en IS NULL) = (motivo_revocacion IS NULL))
);

CREATE INDEX ix_sesion_usuario_id_vigente ON sesion (usuario_id) WHERE revocada_en IS NULL;
