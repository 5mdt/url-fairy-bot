ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-alpine AS builder

RUN apk add --no-cache --virtual .build-deps \
        build-base  \
        libffi-dev \
        openssl-dev \
        curl \
    && pip install --no-cache-dir uv==0.12.11 \
    && rm -rf /root/.cache/pip

WORKDIR /app

COPY ./pyproject.toml ./uv.lock ./README.md /app/
COPY ./app /app/app

RUN uv sync --frozen --no-dev --no-editable \
    && rm -rf /root/.cache/uv


FROM python:${PYTHON_VERSION}-alpine

RUN apk add --no-cache ffmpeg

WORKDIR /app

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /app /app
COPY entrypoint.sh /

VOLUME [ "/tmp/url-fairy-bot-cache/" ]

ENV PYTHONPATH="/app"

HEALTHCHECK --interval=2s --timeout=2s --start-period=5s --retries=30 \
    CMD wget -q -O /dev/null http://127.0.0.1:8000/health || exit 1

CMD ["/entrypoint.sh"]
