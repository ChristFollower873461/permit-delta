# ==========================================
# Stage 1: Build the React TypeScript Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend source files and install dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Build the FastAPI Python 3.12 Backend
# ==========================================
FROM python:3.12-slim AS backend-runner
WORKDIR /app

# Copy backend requirements and install dependencies cleanly
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy built frontend SPA assets to the backend-served folder
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose FastAPI default port
EXPOSE 8000

# Set environment defaults
ENV HOST=0.0.0.0
ENV PORT=8000
ENV LIVE_PARTNERS=False

# Run using Uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
