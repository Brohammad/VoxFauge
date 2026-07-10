FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY dashboard ./dashboard
COPY examples ./examples
COPY public ./public
COPY scripts ./scripts

RUN chmod +x /app/scripts/docker-entrypoint.sh
RUN pip install --no-cache-dir -e ".[dev,livekit]"

EXPOSE 8000

CMD ["uvicorn", "voxforge.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/src"]
