# Multi-stage Dockerfile for development and production

# Base stage with common setup
FROM python:3.13-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    'build-essential=12.9' \
    'libpq-dev=15.13-0+deb12u1' \
    'curl=7.88.1-10+deb12u12' \
    'gettext=0.21-12' \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir 'poetry<3' 'poetry-plugin-export<2'

# Copy dependency files
COPY pyproject.toml poetry.lock /app/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=ludamus.config.settings

# Development stage with dev dependencies
FROM base AS dev

# Export all dependencies including dev
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --with dev \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src

# Create necessary directories and set ownership
RUN mkdir -p staticfiles media logs \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Development command - runserver with reload
CMD ["python", "src/manage.py", "runserver", "0.0.0.0:8000"]

# Production stage without dev dependencies
FROM base AS prod

# Export only production dependencies
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src

# Create necessary directories and set ownership
RUN mkdir -p staticfiles media logs \
    && chown -R appuser:appuser /app

# Accept build args and set as env vars for the build
ARG SECRET_KEY
ARG STATIC_ROOT
ENV ENV=production

# Switch to non-root user
USER appuser

WORKDIR /app/src

# Compile translation messages
RUN django-admin compilemessages

# Collect static files (requires SECRET_KEY to be set)
RUN django-admin collectstatic --noinput

# Create cache table for production
RUN django-admin createcachetable || true

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Production command using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--worker-class", "sync", "--worker-tmp-dir", "/dev/shm", "--access-logfile", "-", "--error-logfile", "-", "--chdir", "/app/src", "ludamus.deploy.wsgi:application"]