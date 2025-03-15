# Use a smaller base image
FROM python:3.11-slim

# Set Poetry version
ARG POETRY_VERSION=2.1.1

# Install dependencies for Poetry and Python builds
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && pip install poetry==${POETRY_VERSION} \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy only dependency files first to leverage Docker cache for dependencies
COPY ./pyproject.toml ./poetry.lock /app/

# Install dependencies, skipping development dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi \
    && rm -rf /root/.cache/pypoetry

# Copy the application code after installing dependencies to avoid rebuilding layers
COPY ./app /app/app
COPY entrypoint.sh /

# Set cache volume
VOLUME [ "/tmp/url-fairy-bot-cache/" ]

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# Set environment variables for Python path
ENV PYTHONPATH="/app"

# Set the command to run the app as a module
CMD [ "/entrypoint.sh" ]
