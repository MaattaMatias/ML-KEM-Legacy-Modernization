# Stage 1: Build C dependencies
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build git libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Install Python deps and compile liboqs on first import (installed to /root/_oqs)
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import oqs; print(oqs.oqs_version())"

# Stage 2: Minimal Production Image
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y libssl3 curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY --from=builder /root/_oqs /root/_oqs

COPY simulation_engine.py .
COPY tests/ tests/

EXPOSE 8080

# Production ASGI server
CMD ["uvicorn", "simulation_engine:app", "--host", "0.0.0.0", "--port", "8080"]
