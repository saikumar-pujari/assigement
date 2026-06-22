FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY assign/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assign/ .
COPY .env .env
COPY Backend_DevOps_Assignment/ /app/data/

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
