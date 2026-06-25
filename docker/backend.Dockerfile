# docker/backend.Dockerfile
FROM python:3.12-slim

WORKDIR /app

# copy Python package source
COPY backend/ /app/backend/

# optional deps
COPY pyproject.toml README.md ./

# install the project (creates compliance in PATH)
RUN pip install --no-cache-dir .

CMD ["sh", "-c", "fastapi dev backend/src/compliance/api/main.py --host 0.0.0.0 --port 8000"]
