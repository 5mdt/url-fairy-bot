FROM python:3.11-alpine

RUN apk add --no-cache --virtual .build-deps \
        build-base  \
        libffi-dev \
        openssl-dev \
        curl \
    && pip install --no-cache-dir uv \
    && apk del .build-deps \
    && rm -rf /root/.cache/pip

WORKDIR /app

COPY ./pyproject.toml ./README.md /app/

RUN uv sync --no-dev --no-editable \
    && rm -rf /root/.cache/uv

COPY ./app /app/app
COPY entrypoint.sh /

VOLUME [ "/tmp/url-fairy-bot-cache/" ]

ENV PYTHONPATH="/app"

CMD ["/entrypoint.sh"]
