FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY mwl_broker ./mwl_broker
# Alembic migrations are part of the image: init_db() brings an existing
# database to head on startup.
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir .

# the C-STORE spool keeps undeliverable instances on disk (mounted volume)
RUN mkdir -p /var/lib/mwl-broker/spool

EXPOSE 8081 11113

# python slim has no curl — use urllib for healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/healthz')"

CMD ["uvicorn", "mwl_broker.main:app", "--host", "0.0.0.0", "--port", "8081"]
