FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY mwl_broker ./mwl_broker
RUN pip install --no-cache-dir .

EXPOSE 8081 11113

# python slim has no curl — use urllib for healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/healthz')"

CMD ["uvicorn", "mwl_broker.main:app", "--host", "0.0.0.0", "--port", "8081"]
