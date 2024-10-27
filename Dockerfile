FROM python:3.11-buster
ARG POETRY_VERSION=1.8.4
RUN pip install poetry==${POETRY_VERSION}

# Copy dependency files and install packages
COPY ./pyproject.toml ./poetry.lock /app/
WORKDIR /app
RUN poetry install --no-root --no-interaction --no-ansi

# Copy application code after dependencies are installed
COPY ./app /app/app

# Set volume for cache
VOLUME [ "/tmp/url-fairy-bot-cache/" ]

# Set environment variables for PYTHONPATH
ENV PYTHONPATH="/app"

# Set the command to run the app as a module
CMD ["poetry", "run", "python", "-m", "app.main"]
