FROM python:3.11-alpine

RUN apk add --no-cache --virtual .build-deps \
        build-base  \
        libffi-dev \
        openssl-dev \
        curl \
    && pip install --no-cache-dir uv==0.12.11 \
    && apk del .build-deps \
    && rm -rf /root/.cache/pip

WORKDIR /app

COPY ./pyproject.toml ./uv.lock ./README.md /app/

RUN uv sync --frozen --no-dev --no-editable \
    && rm -rf /root/.cache/uv

COPY ./app /app/app
COPY entrypoint.sh /

VOLUME [ "/tmp/url-fairy-bot-cache/" ]

ENV PYTHONPATH="/app"

HEALTHCHECK --interval=2s --timeout=2s --start-period=5s --retries=30 \
    CMD wget -q -O /dev/null http://127.0.0.1:8000/health || exit 1

CMD ["/entrypoint.sh"]
