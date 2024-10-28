# Use a Python base image
FROM python:3.11-buster

# Set the Poetry version as a build argument and install it
ARG POETRY_VERSION=1.8.2
RUN pip install poetry==${POETRY_VERSION}

# Copy dependency files and install packages
COPY ./pyproject.toml ./poetry.lock /app/
WORKDIR /app
RUN poetry install --no-root --no-interaction --no-ansi

# Copy application code after dependencies are installed
COPY ./app /app/app
COPY entrypoint.sh /

# Set volume for cache
VOLUME [ "/tmp/url-fairy-bot-cache/" ]

# Set environment variables for PYTHONPATH
ENV PYTHONPATH="/app"

# Set the command to run the app as a module
CMD [ "/entrypoint.sh" ]
