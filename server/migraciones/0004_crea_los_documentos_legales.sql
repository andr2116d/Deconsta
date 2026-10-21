-- Términos de uso y política de privacidad versionados, y la aceptación de cada cuenta.
-- Un documento publicado no se edita: un texto nuevo es una versión nueva (en otra migración) y
-- las cuentas deben aceptarla para seguir. Rige la versión más alta de cada tipo cuya fecha
-- vigente_desde ya llegó. Las aceptaciones son la constancia del consentimiento y, como la
-- auditoría, solo admiten inserciones.

CREATE FUNCTION impedir_cambios() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % no admite %', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TABLE documento_legal (
    id bigint GENERATED ALWAYS AS IDENTITY,
    tipo text NOT NULL,
    version integer NOT NULL,
    titulo text NOT NULL,
    resumen text NOT NULL,
    -- [{"titulo": "...", "parrafos": ["...", ...]}, ...]: texto plano, sin HTML.
    secciones jsonb NOT NULL,
    vigente_desde timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_documento_legal PRIMARY KEY (id),
    CONSTRAINT uq_documento_legal_tipo_version UNIQUE (tipo, version),
    CONSTRAINT ck_documento_legal_tipo CHECK (tipo IN ('terminos', 'privacidad')),
    CONSTRAINT ck_documento_legal_version CHECK (version >= 1),
    CONSTRAINT ck_documento_legal_secciones
        CHECK (jsonb_typeof(secciones) = 'array' AND jsonb_array_length(secciones) > 0)
);

CREATE TABLE aceptacion_documento (
    id bigint GENERATED ALWAYS AS IDENTITY,
    usuario_id uuid NOT NULL,
    documento_id bigint NOT NULL,
    aceptada_en timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_aceptacion_documento PRIMARY KEY (id),
    CONSTRAINT fk_aceptacion_documento_usuario_id_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    CONSTRAINT fk_aceptacion_documento_documento_id_documento_legal
        FOREIGN KEY (documento_id) REFERENCES documento_legal (id),
    -- Cada cuenta acepta cada versión una sola vez.
    CONSTRAINT uq_aceptacion_documento_usuario_documento UNIQUE (usuario_id, documento_id)
);

CREATE INDEX ix_aceptacion_documento_documento_id ON aceptacion_documento (documento_id);

CREATE TRIGGER tg_documento_legal_inmutable
    BEFORE UPDATE OR DELETE ON documento_legal
    FOR EACH ROW EXECUTE FUNCTION impedir_cambios();

CREATE TRIGGER tg_documento_legal_sin_truncate
    BEFORE TRUNCATE ON documento_legal
    FOR EACH STATEMENT EXECUTE FUNCTION impedir_cambios();

CREATE TRIGGER tg_aceptacion_documento_inmutable
    BEFORE UPDATE OR DELETE ON aceptacion_documento
    FOR EACH ROW EXECUTE FUNCTION impedir_cambios();

CREATE TRIGGER tg_aceptacion_documento_sin_truncate
    BEFORE TRUNCATE ON aceptacion_documento
    FOR EACH STATEMENT EXECUTE FUNCTION impedir_cambios();

INSERT INTO documento_legal (tipo, version, titulo, resumen, secciones) VALUES
(
    'terminos',
    1,
    'Términos de uso',
    'Cómo funciona tu espacio en Deconsta y qué responsabilidades tiene cada rol.',
    $json$[
        {
            "titulo": "Qué es Deconsta",
            "parrafos": [
                "Deconsta es un espacio de trabajo para organizar las obligaciones de pago de un gerente con el apoyo de sus asistentes: registrar deudas y servicios, autorizarlos, dejar constancia de cada pago y conservar su historial.",
                "Deconsta no mueve dinero. Los pagos se realizan fuera del sistema y aquí se registra su comprobante. Todos los importes se expresan en soles (PEN)."
            ]
        },
        {
            "titulo": "Tu cuenta",
            "parrafos": [
                "Tu cuenta es personal e intransferible. Mantén tu contraseña en reserva y no la compartas, ni siquiera con tu gerente o con tu equipo.",
                "Cada acción que realizas queda registrada a tu nombre. Si sospechas que alguien conoce tu contraseña, cámbiala y avisa a tu gerente."
            ]
        },
        {
            "titulo": "Responsabilidades de cada rol",
            "parrafos": [
                "El gerente registra gastos, autoriza excepciones, asigna pagos a sus asistentes, revisa los comprobantes y administra las cuentas de su equipo.",
                "La asistente registra gastos, corrige sus registros y adjunta los comprobantes de los pagos que se le encargan. No autoriza ni verifica pagos ni administra otras cuentas."
            ]
        },
        {
            "titulo": "Uso adecuado",
            "parrafos": [
                "Registra solo información verdadera y documentos que te correspondan o que tu gerente te haya encargado.",
                "No intentes acceder a información de otras cuentas ni evitar las autorizaciones, los límites o los controles del sistema."
            ]
        },
        {
            "titulo": "Historial y constancia",
            "parrafos": [
                "Los ingresos, los cambios de contraseña, las autorizaciones, los rechazos y los pagos quedan en un historial que no puede modificarse desde la aplicación."
            ]
        },
        {
            "titulo": "Cambios en estos términos",
            "parrafos": [
                "Si estos términos cambian, publicaremos una versión nueva y te pediremos aceptarla antes de seguir usando Deconsta."
            ]
        }
    ]$json$::jsonb
),
(
    'privacidad',
    1,
    'Política de privacidad',
    'Qué datos personales tratamos, para qué los usamos y cómo ejerces tus derechos.',
    $json$[
        {
            "titulo": "Qué datos tratamos",
            "parrafos": [
                "Tus nombres y apellidos, tu tipo y número de documento, tu correo, tu teléfono si lo diste, tu usuario y tu rol, y el registro de tus ingresos y acciones.",
                "También los documentos que registres, como recibos, contratos y comprobantes de pago.",
                "Tu contraseña se guarda solo como un hash irreversible: nadie puede leerla."
            ]
        },
        {
            "titulo": "Para qué los usamos",
            "parrafos": [
                "Para identificarte y proteger tu cuenta, organizar las obligaciones y los pagos de tu equipo, avisarte de los vencimientos y dejar constancia de las decisiones.",
                "No usamos tus datos para publicidad ni los vendemos."
            ]
        },
        {
            "titulo": "Quién puede verlos",
            "parrafos": [
                "Tu gerente y las asistentes de su equipo ven la información del trabajo que comparten. Una asistente solo ve sus propios registros y encargos.",
                "No cedemos tus datos a terceros, salvo por mandato legal."
            ]
        },
        {
            "titulo": "Cómo los protegemos",
            "parrafos": [
                "Los datos personales se guardan cifrados, la sesión viaja en una cookie protegida y lo que ves depende de tu rol."
            ]
        },
        {
            "titulo": "Cuánto tiempo los conservamos",
            "parrafos": [
                "Mientras tu cuenta esté activa y, después, durante el plazo necesario para cumplir obligaciones legales o atender reclamos."
            ]
        },
        {
            "titulo": "Tus derechos",
            "parrafos": [
                "Conforme a la Ley N.° 29733, Ley de Protección de Datos Personales, y su reglamento, puedes solicitar el acceso, la rectificación, la cancelación o la oposición al tratamiento de tus datos (derechos ARCO) y revocar tu consentimiento.",
                "Si tu solicitud no es atendida, puedes acudir a la Autoridad Nacional de Protección de Datos Personales."
            ]
        }
    ]$json$::jsonb
);
