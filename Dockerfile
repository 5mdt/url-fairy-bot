FROM python:3.11-buster
ARG POETRY_VERSION=1.8.2
RUN pip install poetry==${POETRY_VERSION}

COPY \
  ./pyproject.toml \
  ./poetry.lock \
  /app/
WORKDIR /app
RUN poetry install --no-root --no-interaction --no-ansi
VOLUME [ "/cache" ]
CMD ["poetry", "run", "python", "/app/main.py"]
COPY ./src /app
