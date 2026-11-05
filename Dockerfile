FROM python:3.14-slim-trixie AS builder
MAINTAINER datapunt@amsterdam.nl

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/


RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv project configuration
COPY pyproject.toml uv.lock ./

ENV CC=/usr/bin/gcc \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Verify the compiler in the same stage and immediately before uv sync

RUN uv sync --frozen --no-install-project --all-groups

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
    PYTHONPATH="/app/src" \
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
