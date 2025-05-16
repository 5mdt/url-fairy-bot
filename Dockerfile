FROM python:3.11-alpine

ARG POETRY_VERSION=2.1.1

RUN apk add --no-cache \
        curl \
        build-base \
        libffi-dev \
        openssl-dev \
        bash \
    && pip install --no-cache-dir poetry==${POETRY_VERSION} \
    && apk del build-base \
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
