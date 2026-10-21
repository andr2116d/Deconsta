-- Reglas de autorización del espacio de cada gerente («Límites y categorías»):
--   - el importe en soles desde el cual lo que registra una asistente espera la autorización
--     del gerente (estrictamente mayor que el límite; sin límite, el importe no detiene nada);
--   - los titulares autorizados: personas o empresas distintas del gerente (su esposa, su empresa)
--     cuyos recibos no piden autorización por titular.
-- Los datos de los titulares son datos personales de terceros: se guardan cifrados con AES-256-GCM
-- desde la aplicación y se buscan por huellas HMAC. Nada se borra: quitar un titular es una baja
-- lógica que conserva la auditoría.

CREATE TABLE regla_autorizacion (
    gerente_id uuid NOT NULL,
    -- Nulo: sin límite de importe.
    limite_importe numeric(12, 2),
    actualizado_por uuid NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_regla_autorizacion PRIMARY KEY (gerente_id),
    CONSTRAINT fk_regla_autorizacion_gerente_id_usuario
        FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_regla_autorizacion_actualizado_por_usuario
        FOREIGN KEY (actualizado_por) REFERENCES usuario (id),
    CONSTRAINT ck_regla_autorizacion_limite_importe
        CHECK (limite_importe > 0 AND limite_importe <= 9999999.99)
);

CREATE TRIGGER tg_regla_autorizacion_actualizado_en
    BEFORE UPDATE ON regla_autorizacion
    FOR EACH ROW EXECUTE FUNCTION fijar_actualizado_en();

CREATE TABLE titular_autorizado (
    id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    nombre_cifrado bytea NOT NULL,
    -- Huella del nombre normalizado: impide repetir a la misma persona.
    nombre_huella bytea NOT NULL,
    -- Cómo se relaciona con el gerente («Esposa», «Mi empresa»). No es un dato sensible.
    relacion text,
    tipo_documento text,
    numero_documento_cifrado bytea,
    numero_documento_huella bytea,
    -- Cuándo declaró el gerente contar con la autorización de esa persona para usar sus datos.
    autorizacion_declarada_en timestamptz NOT NULL,
    creado_por uuid NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    quitado_en timestamptz,
    CONSTRAINT pk_titular_autorizado PRIMARY KEY (id),
    CONSTRAINT fk_titular_autorizado_gerente_id_usuario
        FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_titular_autorizado_creado_por_usuario
        FOREIGN KEY (creado_por) REFERENCES usuario (id),
    CONSTRAINT ck_titular_autorizado_tipo_documento
        CHECK (tipo_documento IN ('dni', 'ce', 'ruc')),
    -- El documento es opcional, pero va completo: tipo, valor cifrado y huella.
    CONSTRAINT ck_titular_autorizado_documento_completo CHECK (
        (tipo_documento IS NULL) = (numero_documento_cifrado IS NULL)
        AND (tipo_documento IS NULL) = (numero_documento_huella IS NULL)
    ),
    CONSTRAINT ck_titular_autorizado_relacion CHECK (char_length(relacion) BETWEEN 1 AND 40)
);

-- Únicos solo entre los vigentes: a alguien quitado se le puede volver a agregar.
CREATE UNIQUE INDEX uq_titular_autorizado_nombre
    ON titular_autorizado (gerente_id, nombre_huella) WHERE quitado_en IS NULL;
CREATE UNIQUE INDEX uq_titular_autorizado_documento
    ON titular_autorizado (gerente_id, numero_documento_huella)
    WHERE quitado_en IS NULL AND numero_documento_huella IS NOT NULL;

CREATE TRIGGER tg_titular_autorizado_actualizado_en
    BEFORE UPDATE ON titular_autorizado
    FOR EACH ROW EXECUTE FUNCTION fijar_actualizado_en();
