FROM python:3.14-slim-trixie AS builder
MAINTAINER datapunt@amsterdam.nl

WORKDIR /app

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv project configuration
COPY pyproject.toml uv.lock ./

ENV CC=/usr/bin/gcc \
    UV_PROJECT_ENVIRONMENT=/app/.venv
# Install uv and dependencies from lockfile
RUN pip install --no-cache-dir uv

# Verify the compiler in the same stage and immediately before uv sync

RUN echo "=== UV VERSION ===" && uv --version && \
    echo "=== PROJECT ENVIRONMENT ===" && echo "$UV_PROJECT_ENVIRONMENT" && \
    echo "=== PROJECT FILES ===" && ls -la /app && \
    uv sync --frozen --no-dev --no-install-project
RUN echo "=== APP DIRECTORY ==="; \
    ls -la /app; \
    echo "=== VENV DIRECTORY ==="; \
    if [ -d /app/.venv ]; then \
        ls -la /app/.venv; \
        ls -la /app/.venv/bin/; \
    else \
        echo "/app/.venv DOES NOT EXIST"; \
    fi; \
    echo "=== POSSIBLE VIRTUAL ENVIRONMENTS ==="; \
    find /app -maxdepth 4 -name pyvenv.cfg -print

# Start runtime image,
FROM python:3.14-slim-trixie
WORKDIR /app
RUN useradd -U -r brpkennisgevingenapi
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy the complete virtual environment, including uWSGI
COPY --from=builder /app/.venv /app/.venv

RUN ls -l /usr/local/bin/python* && \
    ls -l /app/.venv/bin/python && \
    /usr/local/bin/python3 --version

COPY . ./

# Have some defaults so the container is easier to start
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=brp_kennisgevingen.settings \
    DJANGO_DEBUG=false \
    UWSGI_HTTP_SOCKET=:8000 \
    UWSGI_MODULE=brp_kennisgevingen.wsgi \
    UWSGI_CALLABLE=application \
    UWSGI_MASTER=1

RUN /app/.venv/bin/python src/manage.py collectstatic --noinput

EXPOSE 8000
USER brpkennisgevingenapi
CMD ["uwsgi"]
