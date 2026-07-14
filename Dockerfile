FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

EXPOSE 11435

ENTRYPOINT ["python", "-m", "backend.main"]
CMD ["--host", "0.0.0.0", "--port", "11435"]
