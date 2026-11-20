FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HS_HOST=0.0.0.0 HS_PORT=8000 HS_DB_PATH=/data/housingsearch.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY housingsearch ./housingsearch
COPY web ./web
COPY data/seed ./data/seed
COPY scripts ./scripts
COPY examples ./examples
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["python", "-m", "housingsearch", "serve"]
