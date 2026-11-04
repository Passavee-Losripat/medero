# Medero API. Build context is the repo root: `fly deploy` uses fly.toml, which points here.
FROM python:3.11-slim
WORKDIR /srv
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY api api
# MOCK demo case and the latest eval report are served by the API (/demo/case, /eval/latest)
COPY data/mock data/mock
COPY eval/results/latest.md eval/results/latest.md
WORKDIR /srv/api
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
