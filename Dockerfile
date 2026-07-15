FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends docker-cli && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
RUN mkdir -p /data && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 11435

ENTRYPOINT ["python", "-m", "backend.main"]
CMD ["--host", "0.0.0.0", "--port", "11435"]
