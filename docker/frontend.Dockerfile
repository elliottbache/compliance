# docker/frontend.Dockerfile
# Locks your base down to Node v22.14.0 (Alpine 3.21) via verified SHA-256 digest
FROM node:25.2.1-alpine3.21@sha256:32509199057d74a987fdd88cde00fdfd48ef52469adbd6bd11969fc701477761

WORKDIR /app

# 2. Copy your frontend directory into the container
COPY frontend/ /app/frontend/

# 3. Change directory into the frontend folder where package.json lives 🚨
WORKDIR /app/frontend

# 4. Install your node package dependencies before running the application 🚨
RUN npm ci --no-audit

# 5. Run your frontend development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]