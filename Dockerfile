# Build from repository root (meter-app/)
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
#RUN npm run build
RUN npx vite build

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /fe/dist ./static
RUN mkdir -p uploads

ENV PYTHONPATH=/app
ENV PORT=10000
EXPOSE 10000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
