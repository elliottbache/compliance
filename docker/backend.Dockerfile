# docker/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# copy Python package source
COPY backend/ /app/backend/

# optional deps
COPY pyproject.toml README.md ./

# install the project (creates compliance in PATH)
RUN pip install --no-cache-dir .

CMD python -m alembic -c backend/alembic.ini upgrade 68c5