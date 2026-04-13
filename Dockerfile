# Stage 1: Build dashboard
FROM node:20-slim AS dashboard-build
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm install --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

# Stage 2: Python API
FROM python:3.12-slim
WORKDIR /app

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend + scripts
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Create data dir and seed database
RUN mkdir -p data && python scripts/seed_manufacturers.py

# Copy built dashboard
COPY --from=dashboard-build /app/dashboard/dist ./dashboard/dist

EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
