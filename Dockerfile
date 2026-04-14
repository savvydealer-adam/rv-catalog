# Stage 1: Build dashboard
FROM node:20-slim AS dashboard-build
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm install --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

# Stage 2: Python API + Playwright
FROM python:3.12-slim
WORKDIR /app

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (includes playwright)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# Copy backend + scripts
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Copy existing data (includes scraped DB) or seed if missing
COPY data/ ./data/
RUN python -c "import sys; sys.path.insert(0, '.'); from backend.database import get_db; db=get_db(); n=db.execute('SELECT COUNT(*) FROM manufacturers').fetchone()[0]; db.close(); exit(0 if n > 0 else 1)" || \
    (python scripts/seed_manufacturers.py && python scripts/seed_forest_river_brands.py)

# Copy built dashboard
COPY --from=dashboard-build /app/dashboard/dist ./dashboard/dist

EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
