# docker/backend.Dockerfile
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# copy Python package source
COPY backend/ /app/backend/

# optional deps
COPY pyproject.toml README.md ./

# install the project (creates compliance in PATH)
RUN pip install --no-cache-dir .

CMD ["sh", "-c", "fastapi dev backend/src/compliance/api/main.py --host 0.0.0.0 --port 8000"]
