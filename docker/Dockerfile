# Multi-stage Dockerfile for development and production

# Base stage with common setup
FROM jdxcode/mise:2026.2 AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gettext=0.23.1-2 curl=8.14.1-2+deb13u2 && rm -rf /var/lib/apt/lists/*

ARG DJANGO_SETTINGS_MODULE
ARG ENV

ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}
ENV ENV=${ENV}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=src
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Copy dependency files
COPY tasks.toml pyproject.toml poetry.lock docker/mise.toml /app/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code
COPY src ./src

# Create necessary directories and set ownership
RUN mkdir -p staticfiles media logs \
    && chown -R appuser:appuser /app \
    && chown -R appuser:appuser /mise

# Development stage with dev dependencies
FROM base AS dev

COPY docker/Procfile.tailwind /app/

# Switch to non-root user
USER appuser

RUN mise trust && mise install && mise run p install ::: dj tailwind install ::: dj compilemessages

# Expose port
EXPOSE 8000

# Development command - runserver with reload
CMD ["mise", "run", "start"]

# Production stage without dev dependencies
FROM base AS prod

COPY docker/Procfile.tailwind /app/

# Switch to non-root user
USER appuser

RUN mise trust && mise install && mise run p install --only main ::: dj tailwind install ::: dj compilemessages

# Expose port
EXPOSE 8000

# Run migrations on startup, then start gunicorn
CMD ["run", "gunicorn"]
