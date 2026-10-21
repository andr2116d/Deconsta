# Imagen del server: la usan la API y el worker de OCR, cada uno con su comando de arranque.
# Lleva el grupo ocr (PaddleOCR) porque el worker lo necesita; la API no lo carga.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# PaddleOCR y OpenCV necesitan estas bibliotecas del sistema.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM base AS construccion
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
# Primero las dependencias: la capa se reutiliza mientras no cambie el lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group ocr --no-install-project
COPY . .
RUN uv sync --locked --no-dev --group ocr

FROM base
# Los modelos de PaddleOCR se guardan en un volumen: la carpeta ya existe con el dueño correcto.
RUN useradd --create-home --uid 10001 app && install -d -o app -g app /home/app/.paddlex
COPY --from=construccion --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
