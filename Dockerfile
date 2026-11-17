# Production image: the API serves the built frontend from one process.
FROM node:26-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production STATIC_DIR=/srv/web
WORKDIR /srv/api
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/alembic.ini .
COPY backend/migrations migrations
COPY backend/app app
COPY --from=web /web/dist /srv/web
RUN useradd --system --no-create-home sampcup
USER sampcup
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
# One worker on purpose: live updates are shared in memory. Only Caddy can reach this port.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
