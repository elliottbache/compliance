# docker/frontend.Dockerfile
# Locks your base down to Node v22.14.0 (Alpine 3.21) via verified SHA-256 digest
FROM node:22.14.0-alpine3.21@sha256:9bef0ef1e268f60627da9ba7d7605e8831d5b56ad07487d24d1aa386336d1944

WORKDIR /app

# 2. Copy your frontend directory into the container
COPY frontend/ /app/frontend/

# 3. Change directory into the frontend folder where package.json lives 🚨
WORKDIR /app/frontend

# 4. Install your node package dependencies before running the application 🚨
RUN npm ci --no-audit

# 5. Run your frontend development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]