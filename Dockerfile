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

# Copy existing data (includes scraped DB) or seed if missing
COPY data/ ./data/
RUN python -c "import os; from pathlib import Path; db=Path('data/rv_catalog.db'); print(f'DB size: {db.stat().st_size if db.exists() else 0}')" && \
    python -c "import sys; sys.path.insert(0, '.'); from backend.database import get_db; db=get_db(); n=db.execute('SELECT COUNT(*) FROM manufacturers').fetchone()[0]; db.close(); print(f'Manufacturers: {n}'); exit(0 if n > 0 else 1)" || \
    python scripts/seed_manufacturers.py

# Copy built dashboard
COPY --from=dashboard-build /app/dashboard/dist ./dashboard/dist

EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
