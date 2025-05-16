FROM python:3.11-alpine

ARG POETRY_VERSION=2.1.1

RUN apk add --no-cache --virtual .build-deps \
        build-base=0.6.3-r0  \
        libffi-dev=3.4.2-r3 \
        openssl-dev=3.0.11-r0 \
    && apk add --no-cache \
        curl=8.2.1-r0 \
        bash=5.1.16-r0 \
    && pip install --no-cache-dir poetry==${POETRY_VERSION} \
    && apk del .build-deps \
    && rm -rf /root/.cache/pip

WORKDIR /app

COPY ./pyproject.toml ./poetry.lock /app/

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi \
    && rm -rf /root/.cache/pypoetry

COPY ./app /app/app
COPY entrypoint.sh /

VOLUME [ "/tmp/url-fairy-bot-cache/" ]

ENV PYTHONPATH="/app"

CMD ["/entrypoint.sh"]
