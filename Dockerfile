FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends docker-cli && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /bin/sh appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /
COPY backend/ backend/
RUN mkdir -p /data && chown -R appuser:appuser /app /data

EXPOSE 11435

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "11435"]
