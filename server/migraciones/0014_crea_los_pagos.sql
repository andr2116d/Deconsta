-- Pagos de las cuotas y los comprobantes (vouchers) que los respaldan.
--
-- Cada comprobante se sube para una cuota de una deuda y se analiza solo: lectura del texto,
-- revisión con IA y metadatos del archivo. Un pago reúne uno o varios comprobantes de esa cuota
-- (un agente puede cobrarla por partes el mismo día) y queda por verificar hasta que el gerente lo
-- confirme; el que registra el gerente queda confirmado. Una cuota tiene a lo más un pago vigente.
--
-- El archivo se guarda cifrado en el almacenamiento de objetos. Lo leído del comprobante (titular,
-- código de pago, número de operación) son datos personales: el análisis se guarda cifrado. Un
-- mismo archivo o una misma operación no respaldan dos pagos del espacio.

CREATE TABLE pago (
    id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    deuda_id uuid NOT NULL,
    cuota integer NOT NULL,
    registrado_por uuid NOT NULL,
    -- Soles (PEN): lo pagado por el servicio, sin la comisión del agente o la ventanilla.
    importe numeric(12, 2) NOT NULL,
    comision numeric(12, 2) NOT NULL DEFAULT 0,
    -- Dónde se pagó, según los comprobantes.
    lugar_pago text,
    pagado_el date NOT NULL,
    estado text NOT NULL,
    -- De 0 a 95: cuánto respaldan los comprobantes que el pago es verdadero. Nunca 100: una
    -- captura no se confirma sin mirar la cuenta que recibió el dinero.
    confianza smallint NOT NULL,
    -- Lo que se comprobó y lo que no, para el gerente. Sin datos personales.
    comprobaciones jsonb NOT NULL DEFAULT '[]',
    registrado_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_pago PRIMARY KEY (id),
    CONSTRAINT fk_pago_gerente_id_usuario FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_pago_registrado_por_usuario FOREIGN KEY (registrado_por) REFERENCES usuario (id),
    CONSTRAINT fk_pago_cuota_deuda
        FOREIGN KEY (deuda_id, cuota) REFERENCES cuota_deuda (deuda_id, numero),
    CONSTRAINT ck_pago_importe CHECK (importe > 0 AND importe <= 9999999.99),
    CONSTRAINT ck_pago_comision CHECK (comision >= 0 AND comision <= 9999999.99),
    CONSTRAINT ck_pago_lugar_pago CHECK (
        lugar_pago IN (
            'ventanilla', 'agente', 'banca_digital', 'transferencia', 'billetera',
            'debito_automatico'
        )
    ),
    CONSTRAINT ck_pago_estado CHECK (estado IN ('por_verificar', 'confirmado')),
    CONSTRAINT ck_pago_confianza CHECK (confianza BETWEEN 0 AND 95)
);

-- Una cuota no se paga dos veces.
CREATE UNIQUE INDEX uq_pago_cuota_vigente ON pago (deuda_id, cuota)
    WHERE estado IN ('por_verificar', 'confirmado');
CREATE INDEX ix_pago_gerente_id_estado ON pago (gerente_id, estado, registrado_en DESC);

CREATE TABLE comprobante_pago (
    id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    subido_por uuid NOT NULL,
    -- La cuota que dice pagar: el análisis lo compara con ella.
    deuda_id uuid NOT NULL,
    cuota integer NOT NULL,
    tipo_archivo text NOT NULL,
    tamano integer NOT NULL,
    paginas integer NOT NULL,
    nombre_archivo_cifrado bytea NOT NULL,
    clave_objeto text NOT NULL,
    -- HMAC del SHA-256 del archivo.
    huella_archivo bytea NOT NULL,
    -- HMAC del número de operación y su fecha: la misma operación en otra foto o captura.
    huella_operacion bytea,
    estado text NOT NULL,
    riesgo text,
    analisis_cifrado bytea,
    subido_en timestamptz NOT NULL DEFAULT now(),
    analizado_en timestamptz,
    -- Pago que respalda. Nulo mientras no se registra.
    pago_id uuid,
    CONSTRAINT pk_comprobante_pago PRIMARY KEY (id),
    CONSTRAINT fk_comprobante_pago_gerente_id_usuario
        FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_comprobante_pago_subido_por_usuario
        FOREIGN KEY (subido_por) REFERENCES usuario (id),
    CONSTRAINT fk_comprobante_pago_cuota_deuda
        FOREIGN KEY (deuda_id, cuota) REFERENCES cuota_deuda (deuda_id, numero),
    CONSTRAINT fk_comprobante_pago_pago_id_pago FOREIGN KEY (pago_id) REFERENCES pago (id),
    CONSTRAINT uq_comprobante_pago_clave_objeto UNIQUE (clave_objeto),
    CONSTRAINT ck_comprobante_pago_tipo_archivo CHECK (
        tipo_archivo IN ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
    ),
    CONSTRAINT ck_comprobante_pago_tamano CHECK (tamano BETWEEN 1 AND 10485760),
    CONSTRAINT ck_comprobante_pago_paginas CHECK (paginas BETWEEN 1 AND 10),
    CONSTRAINT ck_comprobante_pago_estado CHECK (
        estado IN ('analizando', 'listo', 'ilegible', 'rechazado', 'repetido', 'fallido')
    ),
    CONSTRAINT ck_comprobante_pago_riesgo CHECK (riesgo IN ('bajo', 'medio', 'alto')),
    -- Solo un comprobante listo respalda un pago.
    CONSTRAINT ck_comprobante_pago_pago_listo CHECK (pago_id IS NULL OR estado = 'listo')
);

-- Un mismo archivo o una misma operación no respaldan dos pagos del espacio.
CREATE UNIQUE INDEX uq_comprobante_pago_archivo_usado
    ON comprobante_pago (gerente_id, huella_archivo) WHERE pago_id IS NOT NULL;
CREATE UNIQUE INDEX uq_comprobante_pago_operacion_usada
    ON comprobante_pago (gerente_id, huella_operacion)
    WHERE pago_id IS NOT NULL AND huella_operacion IS NOT NULL;
CREATE INDEX ix_comprobante_pago_pago_id ON comprobante_pago (pago_id);

-- Comprobantes que el análisis rechazó porque no corresponden (repetidos, alterados, de otra
-- deuda) y el bloqueo del registro de pagos al tercero en 24 horas. Los ilegibles no cuentan. El
-- bloqueo no toca la cuenta ni el registro de deudas. Los intentos solo admiten inserciones.

CREATE TABLE intento_comprobante_rechazado (
    id bigint GENERATED ALWAYS AS IDENTITY,
    asistente_id uuid NOT NULL,
    comprobante_id uuid NOT NULL,
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_intento_comprobante_rechazado PRIMARY KEY (id),
    CONSTRAINT fk_intento_comprobante_rechazado_asistente_id_usuario
        FOREIGN KEY (asistente_id) REFERENCES usuario (id),
    -- El nombre completo pasaría de los 63 caracteres que admite Postgres.
    CONSTRAINT fk_intento_comprobante_rechazado_comprobante_id
        FOREIGN KEY (comprobante_id) REFERENCES comprobante_pago (id)
);

CREATE INDEX ix_intento_comprobante_rechazado_asistente_id
    ON intento_comprobante_rechazado (asistente_id, ocurrido_en DESC);

CREATE TRIGGER tg_intento_comprobante_rechazado_inmutable
    BEFORE UPDATE OR DELETE ON intento_comprobante_rechazado
    FOR EACH ROW EXECUTE FUNCTION impedir_cambios_auditoria();

CREATE TABLE bloqueo_registro_pago (
    id uuid NOT NULL,
    asistente_id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    bloqueado_en timestamptz NOT NULL DEFAULT now(),
    levantado_en timestamptz,
    levantado_por uuid,
    CONSTRAINT pk_bloqueo_registro_pago PRIMARY KEY (id),
    CONSTRAINT fk_bloqueo_registro_pago_asistente_id_usuario
        FOREIGN KEY (asistente_id) REFERENCES usuario (id),
    CONSTRAINT fk_bloqueo_registro_pago_gerente_id_usuario
        FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_bloqueo_registro_pago_levantado_por_usuario
        FOREIGN KEY (levantado_por) REFERENCES usuario (id),
    CONSTRAINT ck_bloqueo_registro_pago_levantamiento
        CHECK ((levantado_en IS NULL) = (levantado_por IS NULL))
);

-- Una asistente tiene a lo más un bloqueo vigente del registro de pagos.
CREATE UNIQUE INDEX uq_bloqueo_registro_pago_vigente
    ON bloqueo_registro_pago (asistente_id) WHERE levantado_en IS NULL;
