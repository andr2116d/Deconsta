-- Categorías del espacio de un gerente (agua, luz, tarjetas…). Ordenan las deudas para filtrarlas,
-- resumirlas y exportarlas. Las comparte todo el equipo: las administra el gerente y sus asistentes
-- las usan. Nunca se borran: archivarlas las retira de las deudas nuevas sin tocar las existentes.

CREATE TABLE categoria (
    id uuid NOT NULL,
    -- Dueño del espacio: el gerente. La aplicación verifica el rol.
    gerente_id uuid NOT NULL,
    nombre text NOT NULL,
    -- Minúsculas, sin tildes y con espacios simples: «Luz» y «  luz » son la misma categoría.
    nombre_normalizado text NOT NULL,
    -- Qué documentos van aquí. Ayudará a la clasificación automática de los recibos.
    descripcion text,
    color text NOT NULL,
    icono text NOT NULL,
    creado_por uuid NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    archivado_en timestamptz,
    CONSTRAINT pk_categoria PRIMARY KEY (id),
    CONSTRAINT fk_categoria_gerente_id_usuario FOREIGN KEY (gerente_id) REFERENCES usuario (id),
    CONSTRAINT fk_categoria_creado_por_usuario FOREIGN KEY (creado_por) REFERENCES usuario (id),
    -- Incluye las archivadas: para volver a usar un nombre se reactiva la categoría.
    CONSTRAINT uq_categoria_gerente_nombre UNIQUE (gerente_id, nombre_normalizado),
    CONSTRAINT ck_categoria_nombre CHECK (char_length(nombre) BETWEEN 2 AND 40),
    CONSTRAINT ck_categoria_nombre_normalizado CHECK (nombre_normalizado <> ''),
    CONSTRAINT ck_categoria_descripcion CHECK (char_length(descripcion) BETWEEN 1 AND 200),
    CONSTRAINT ck_categoria_color CHECK (
        color IN ('ciruela', 'coral', 'ambar', 'oliva', 'verde', 'azul', 'lavanda', 'grafito')
    ),
    CONSTRAINT ck_categoria_icono CHECK (
        icono IN (
            'agua', 'luz', 'gas', 'telefono', 'internet', 'tarjeta', 'banco', 'impuestos',
            'vivienda', 'transporte', 'salud', 'educacion', 'seguro', 'etiqueta'
        )
    )
);

CREATE TRIGGER tg_categoria_actualizado_en
    BEFORE UPDATE ON categoria
    FOR EACH ROW EXECUTE FUNCTION fijar_actualizado_en();
