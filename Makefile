.DEFAULT_GOAL := help
.PHONY: help install sync fmt lint yamllint check test test-cov run pre-commit \
	docker-build docker-up docker-down docker-logs docker-restart deploy-check clean

UV := uv
COMPOSE_DEV := sudo docker compose -f docker-compose.yml -f compose.dev.yml

## help: Show this help
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed -E 's/^## //' | column -t -s ':'

## install: Create/sync the .venv with all dependency groups
install:
	$(UV) sync --all-groups

## sync: Alias for install
sync: install

## fmt: Format code with black and isort
fmt:
	$(UV) run black ./app
	$(UV) run isort ./app

## lint: Run flake8
lint:
	$(UV) run flake8 ./app

## yamllint: Lint YAML files (project files only, .venv excluded)
yamllint:
	$(UV) run yamllint --no-warnings -s docker-compose.yml compose.dev.yml .github .pre-commit-config.yaml

## check: Run fmt, lint, yamllint and tests (use before/after any change)
check: fmt lint yamllint test

## test: Run the test suite
test:
	$(UV) run pytest

## run: Run the app locally with uvicorn (reload enabled)
run:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

## pre-commit: Run all pre-commit hooks against all files
pre-commit:
	$(UV) run pre-commit run --all-files

## docker-build: Build the app image from source (dev override)
docker-build:
	$(COMPOSE_DEV) build

## docker-up: Start the stack in the background, built from source (dev override)
docker-up:
	$(COMPOSE_DEV) up -d

## docker-down: Stop and remove the stack
docker-down:
	$(COMPOSE_DEV) down

## docker-logs: Follow app logs
docker-logs:
	$(COMPOSE_DEV) logs -f app

## docker-restart: Restart the stack
docker-restart: docker-down docker-up

## deploy-check: Validate the registry-only production compose file alone
deploy-check:
	sudo docker compose -f docker-compose.yml config -q

## clean: Remove caches and build artifacts
clean:
	rm -rf .pytest_cache .ruff_cache .coverage build dist
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} +
