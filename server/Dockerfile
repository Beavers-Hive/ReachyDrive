FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run expects the port to be defined in the PORT environment variable
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port \${PORT:-8080}"
