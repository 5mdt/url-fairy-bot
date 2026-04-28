# ----------------------------
# Builder stage
# ----------------------------
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-alpine AS builder

ARG POETRY_VERSION=2.3.4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache --virtual .build-deps \
        build-base \
        cargo \
        libffi-dev \
        openssl-dev \
        python3-dev \
    && true # for easier formatting

RUN python -m ensurepip \
    && pip install --no-cache-dir poetry==${POETRY_VERSION}

COPY pyproject.toml poetry.lock /app/

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi \
    && rm -rf /root/.cache/pypoetry


# ----------------------------
# Runtime stage
# ----------------------------
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache \
        libffi \
        libstdc++ \
        openssl \
        tzdata \
    && addgroup -S appgroup \
    && adduser -S appuser -G appgroup \
    && mkdir -p /tmp/url-fairy-bot-cache/ \
    && chown appuser:appgroup /tmp/url-fairy-bot-cache/

COPY --from=builder /usr/local /usr/local

COPY ./app /app/app
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && chown appuser:appgroup /entrypoint.sh \
    && chown -R appuser:appgroup /app

USER appuser

ENTRYPOINT ["/entrypoint.sh"]
