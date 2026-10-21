-- Gestión del equipo desde «Mi equipo»: el gerente registra, bloquea, elimina y recupera a sus
-- asistentes. Nada se borra de verdad: una asistente eliminada queda marcada (eliminada_en) para
-- conservar la auditoría y poder recuperarla. Ningún dato existente se pierde.

-- Por qué está bloqueada la cuenta: por intentos fallidos o porque su gerente la bloqueó.
ALTER TABLE usuario ADD COLUMN causa_bloqueo text;
UPDATE usuario SET causa_bloqueo = 'intentos_fallidos' WHERE bloqueada_en IS NOT NULL;
ALTER TABLE usuario
    ADD CONSTRAINT ck_usuario_causa_bloqueo
        CHECK (causa_bloqueo IN ('intentos_fallidos', 'gerente')),
    ADD CONSTRAINT ck_usuario_bloqueo_con_causa
        CHECK ((bloqueada_en IS NULL) = (causa_bloqueo IS NULL));

-- Baja lógica: solo de asistentes.
ALTER TABLE usuario
    ADD COLUMN eliminada_en timestamptz,
    ADD CONSTRAINT ck_usuario_eliminacion_asistente
        CHECK (eliminada_en IS NULL OR rol = 'asistente');

-- La asistente confirma sus datos en su primer ingreso (paso obligatorio). Las cuentas existentes
-- ya tienen sus datos completos y se dan por confirmadas.
ALTER TABLE usuario ADD COLUMN datos_confirmados_en timestamptz;
UPDATE usuario SET datos_confirmados_en = creado_en;

-- El gerente registra a la asistente sin correo: ella lo completa al confirmar sus datos.
ALTER TABLE usuario
    ALTER COLUMN correo_cifrado DROP NOT NULL,
    ALTER COLUMN correo_huella DROP NOT NULL,
    ADD CONSTRAINT ck_usuario_correo_huella
        CHECK ((correo_cifrado IS NULL) = (correo_huella IS NULL)),
    ADD CONSTRAINT ck_usuario_correo_obligatorio
        CHECK (correo_cifrado IS NOT NULL OR (rol = 'asistente' AND datos_confirmados_en IS NULL));

-- El correo y el documento son únicos solo entre cuentas no eliminadas: una persona eliminada
-- puede volver con una cuenta nueva. Los índices conservan el nombre de las restricciones que
-- reemplazan, así el error de duplicado sigue apuntando al mismo campo.
ALTER TABLE usuario
    DROP CONSTRAINT uq_usuario_correo_huella,
    DROP CONSTRAINT uq_usuario_documento_huella;
CREATE UNIQUE INDEX uq_usuario_correo_huella
    ON usuario (correo_huella) WHERE eliminada_en IS NULL;
CREATE UNIQUE INDEX uq_usuario_documento_huella
    ON usuario (tipo_documento, numero_documento_huella) WHERE eliminada_en IS NULL;
-- Para encontrar también a las eliminadas al registrar a alguien con el mismo documento.
CREATE INDEX ix_usuario_documento_huella ON usuario (tipo_documento, numero_documento_huella);
