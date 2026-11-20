# Runs locally (docker compose), on Hugging Face Spaces, or on any container host.
# Spaces runs containers as uid 1000, so the app runs as a non-root user and keeps
# its SQLite database in a folder that user owns.
FROM python:3.12-slim

RUN useradd -m -u 1000 user \
 && mkdir -p /data && chown user:user /data   # mount point for docker-compose / HF persistent storage

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HS_HOST=0.0.0.0 \
    HS_DB_PATH=/home/user/app/data/housingsearch.db
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user housingsearch ./housingsearch
COPY --chown=user web ./web
COPY --chown=user data/seed ./data/seed
COPY --chown=user scripts ./scripts
COPY --chown=user examples ./examples

EXPOSE 8000
# Listens on $PORT when the host sets it (Render, Railway, Cloud Run…), otherwise 8000.
HEALTHCHECK CMD python -c "import os,urllib.request;urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('PORT','8000'))" || exit 1
CMD ["python", "-m", "housingsearch", "serve"]
