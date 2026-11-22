# The ledger as a Cloud Run service (deploy/ledger/deploy.sh builds this; it is not needed locally).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 LEDGER_STORE=firestore
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ledger ./ledger
# one process (the status cache and rate limits are per process), many threads
CMD exec gunicorn --bind ":${PORT:-8080}" --workers 1 --threads 16 --timeout 120 'ledger.api:create_app()'
