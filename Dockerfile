# Learnova: one container with the API, the built web app, LibreOffice (PPTX → PDF) and Tesseract (OCR).
#   docker build -t learnova . && docker run -p 8000:8000 --env-file .env learnova
FROM node:20-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 LEARNOVA_SERVE_WEB=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-impress libreoffice-writer tesseract-ocr wamerican fonts-dejavu fonts-liberation nodejs \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY src/ src/
COPY apps/ apps/
COPY data/ data/
COPY pyproject.toml ./
COPY --from=web /web/dist frontend/dist
ENV PYTHONPATH=/app/src:/app
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
