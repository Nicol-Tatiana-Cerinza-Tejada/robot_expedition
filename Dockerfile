# Imagen de la API de Robot Expedition (FastAPI + MuJoCo + modelos).
# Pensada para Hugging Face Spaces (SDK docker, puerto 7860); sirve igual en Render o local.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r api/requirements.txt

COPY --chown=user . .

# Identidad del codigo servido: docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) --build-arg RELEASE=v1.0
ARG GIT_COMMIT=desconocido
ARG RELEASE=sin-release
ENV GIT_COMMIT=$GIT_COMMIT RELEASE=$RELEASE API_DVC_PULL=1 PORT=7860

USER user
EXPOSE 7860
CMD ["sh", "api/start.sh"]
