-- Deudas del espacio de un gerente y el documento que respalda cada una (recibo, boleta, factura,
-- cronograma de un préstamo, papeleta…). Toda deuda nace de un documento legible y cada documento
-- respalda una sola deuda: el archivo y su clave de negocio no se repiten dentro del espacio.
--
-- El archivo se guarda cifrado con AES-256-GCM en el almacenamiento de objetos; aquí solo queda su
-- ubicación. Lo que se lee del documento (titular, código de pago…) son datos personales: el
-- análisis se guarda cifrado y, en la deuda, el titular y el código de pago también.

CREATE TABLE documento_deuda (
    id uuid NOT NULL,
    -- Dueño del espacio: el gerente. La aplicación verifica el rol.
    gerente_id uuid NOT NULL,
    subido_por uuid NOT NULL,
    tipo_archivo text NOT NULL,
    tamano integer NOT NULL,
    paginas integer NOT NULL,
    nombre_archivo_cifrado bytea NOT NULL,
    clave_objeto text NOT NULL,
    -- HMAC del SHA-256 del archivo: el mismo archivo da la misma huella.
    huella_archivo bytea NOT NULL,
    -- HMAC de la clave de negocio (emisor, serie y número; empresa, suministro y periodo…): el
    -- mismo documento escaneado o fotografiado otra vez da la misma huella.
    clave_negocio_huella bytea,
    -- HMAC de los números largos del texto leído: identifica el documento cuando no se pudo armar
    -- su clave de negocio.
    huellas_texto bytea[] NOT NULL DEFAULT '{}',
    estado text NOT NULL,
    tipo_documento text,
    riesgo text,
    analisis_cifrado bytea,
    -- Deuda ya registrada con este documento, cuando se intentó subirlo otra vez.
    repetido_de uuid,
    subido_en timestamptz NOT NULL DEFAULT now(),
    analizado_en timestamptz,
    -- Deuda que respalda. Nulo mientras no se registra.
    deuda_id uuid,
    CONSTRAINT pk_documento_deuda PRIMARY KEY (id),
    CONSTRAINT fk_documento_deuda_gerente_id_usuario
        FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_documento_deuda_subido_por_usuario
        FOREIGN KEY (subido_por) REFERENCES usuario (id),
    CONSTRAINT uq_documento_deuda_clave_objeto UNIQUE (clave_objeto),
    CONSTRAINT uq_documento_deuda_deuda_id UNIQUE (deuda_id),
    CONSTRAINT ck_documento_deuda_tipo_archivo CHECK (
        tipo_archivo IN ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
    ),
    CONSTRAINT ck_documento_deuda_tamano CHECK (tamano BETWEEN 1 AND 10485760),
    CONSTRAINT ck_documento_deuda_paginas CHECK (paginas BETWEEN 1 AND 10),
    CONSTRAINT ck_documento_deuda_estado CHECK (
        estado IN ('analizando', 'listo', 'ilegible', 'repetido', 'rechazado', 'fallido')
    ),
    CONSTRAINT ck_documento_deuda_tipo_documento CHECK (
        tipo_documento IN (
            'recibo_servicio', 'boleta', 'factura', 'cronograma', 'papeleta', 'tributo', 'otro'
        )
    ),
    CONSTRAINT ck_documento_deuda_riesgo CHECK (riesgo IN ('bajo', 'medio', 'alto')),
    -- Solo un documento listo respalda una deuda.
    CONSTRAINT ck_documento_deuda_deuda_lista CHECK (deuda_id IS NULL OR estado = 'listo')
);

-- Un mismo archivo o una misma clave de negocio no respaldan dos deudas del espacio.
CREATE UNIQUE INDEX uq_documento_deuda_archivo_registrado
    ON documento_deuda (gerente_id, huella_archivo) WHERE deuda_id IS NOT NULL;
CREATE UNIQUE INDEX uq_documento_deuda_clave_registrada
    ON documento_deuda (gerente_id, clave_negocio_huella)
    WHERE deuda_id IS NOT NULL AND clave_negocio_huella IS NOT NULL;
CREATE INDEX ix_documento_deuda_huellas_texto
    ON documento_deuda USING gin (huellas_texto) WHERE deuda_id IS NOT NULL;
CREATE INDEX ix_documento_deuda_subido_por ON documento_deuda (subido_por, subido_en DESC);

CREATE TABLE deuda (
    id uuid NOT NULL,
    gerente_id uuid NOT NULL,
    registrada_por uuid NOT NULL,
    documento_id uuid NOT NULL,
    concepto text NOT NULL,
    -- Nula: «Otros».
    categoria_id uuid,
    tipo_documento text NOT NULL,
    -- Soles (PEN), la única moneda. Es la suma de sus cuotas.
    importe numeric(12, 2) NOT NULL,
    -- Vencimiento de la primera cuota.
    vence_el date NOT NULL,
    lugar_pago text NOT NULL,
    titular_cifrado bytea,
    titular_tipo_documento text,
    titular_documento_cifrado bytea,
    codigo_pago_cifrado bytea,
    estado text NOT NULL,
    -- Por qué espera la autorización del gerente (IMPORTE_SOBRE_LIMITE, TITULAR_DISTINTO…).
    motivos_autorizacion text[] NOT NULL DEFAULT '{}',
    -- Lo que registró una asistente sin excepciones: el gerente aún no le da su visto bueno.
    revision_pendiente boolean NOT NULL DEFAULT false,
    -- Campos que se corrigieron a mano respecto de lo leído en el documento.
    campos_corregidos text[] NOT NULL DEFAULT '{}',
    decidida_por uuid,
    decidida_en timestamptz,
    motivo_decision text,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_deuda PRIMARY KEY (id),
    CONSTRAINT fk_deuda_gerente_id_usuario FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_deuda_registrada_por_usuario
        FOREIGN KEY (registrada_por) REFERENCES usuario (id),
    CONSTRAINT fk_deuda_documento_id_documento_deuda
        FOREIGN KEY (documento_id) REFERENCES documento_deuda (id),
    CONSTRAINT fk_deuda_categoria_id_categoria FOREIGN KEY (categoria_id) REFERENCES categoria (id),
    CONSTRAINT fk_deuda_decidida_por_usuario FOREIGN KEY (decidida_por) REFERENCES usuario (id),
    CONSTRAINT uq_deuda_documento_id UNIQUE (documento_id),
    CONSTRAINT ck_deuda_concepto CHECK (char_length(concepto) BETWEEN 2 AND 80),
    CONSTRAINT ck_deuda_importe CHECK (importe > 0 AND importe <= 9999999.99),
    CONSTRAINT ck_deuda_lugar_pago CHECK (
        lugar_pago IN (
            'ventanilla', 'agente', 'banca_digital', 'transferencia', 'billetera',
            'debito_automatico'
        )
    ),
    CONSTRAINT ck_deuda_titular_tipo_documento
        CHECK (titular_tipo_documento IN ('dni', 'ce', 'ruc')),
    CONSTRAINT ck_deuda_titular_documento_completo CHECK (
        (titular_tipo_documento IS NULL) = (titular_documento_cifrado IS NULL)
    ),
    CONSTRAINT ck_deuda_estado
        CHECK (estado IN ('por_autorizar', 'registrada', 'rechazada', 'anulada')),
    CONSTRAINT ck_deuda_revision_registrada CHECK (NOT revision_pendiente OR estado = 'registrada'),
    -- Rechazar o anular siempre deja su motivo.
    CONSTRAINT ck_deuda_motivo_decision CHECK (
        estado NOT IN ('rechazada', 'anulada') OR char_length(motivo_decision) BETWEEN 1 AND 500
    )
);

CREATE INDEX ix_deuda_gerente_id_estado ON deuda (gerente_id, estado, creado_en DESC);
CREATE INDEX ix_deuda_registrada_por ON deuda (registrada_por, creado_en DESC);

ALTER TABLE documento_deuda
    ADD CONSTRAINT fk_documento_deuda_deuda_id_deuda FOREIGN KEY (deuda_id) REFERENCES deuda (id),
    ADD CONSTRAINT fk_documento_deuda_repetido_de_deuda
        FOREIGN KEY (repetido_de) REFERENCES deuda (id);

CREATE TRIGGER tg_deuda_actualizado_en
    BEFORE UPDATE ON deuda
    FOR EACH ROW EXECUTE FUNCTION fijar_actualizado_en();

-- Cada deuda tiene al menos una cuota. Un recibo es una sola cuota; un préstamo, las de su
-- cronograma, que pueden tener importes distintos.
CREATE TABLE cuota_deuda (
    deuda_id uuid NOT NULL,
    numero integer NOT NULL,
    vence_el date NOT NULL,
    importe numeric(12, 2) NOT NULL,
    CONSTRAINT pk_cuota_deuda PRIMARY KEY (deuda_id, numero),
    CONSTRAINT fk_cuota_deuda_deuda_id_deuda FOREIGN KEY (deuda_id) REFERENCES deuda (id),
    CONSTRAINT ck_cuota_deuda_numero CHECK (numero BETWEEN 1 AND 360),
    CONSTRAINT ck_cuota_deuda_importe CHECK (importe > 0 AND importe <= 9999999.99)
);

CREATE INDEX ix_cuota_deuda_vence_el ON cuota_deuda (vence_el);
