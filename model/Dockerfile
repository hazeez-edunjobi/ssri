# SSRI model package — shared image for API and Celery worker
# Build context must be the model/ directory.
# CPU torch only — poetry.lock resolves torch 2.13 with CUDA deps on Linux;
# those wheels are filtered out of the install set.

FROM python:3.11-slim-bookworm AS builder

ENV POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}" "poetry-plugin-export==1.8.0"

COPY pyproject.toml poetry.lock README.md ./
COPY src ./src
COPY docker/filter_cpu_requirements.py /tmp/filter_cpu_requirements.py

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.5.1" \
    && poetry export --only main --without-hashes -o /tmp/requirements.txt \
    && python /tmp/filter_cpu_requirements.py /tmp/requirements.txt /tmp/requirements.cpu.txt \
    && pip install --no-cache-dir -r /tmp/requirements.cpu.txt \
    && pip install --no-cache-dir --no-deps .

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SSRI_API_OUTPUT_ROOT=/data/outputs \
    PYTHONPATH=/app/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libexpat1 \
        libsqlite3-0 \
        libcurl4 \
        libssl3 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home app \
    && mkdir -p /data/outputs /data/auth /data/jobs \
    && chown -R app:app /data

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=app:app /build/src /app/src
COPY --chown=app:app docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

USER root
# Pre-download WhiteboxTools Linux binary so the non-root app user does not
# attempt a first-use write into site-packages (PermissionError on live DEM).
RUN python -c "from whitebox.whitebox_tools import download_wbt; download_wbt(verbose=False)" \
    && chown -R app:app /usr/local/lib/python3.11/site-packages/whitebox \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh
USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["api"]
