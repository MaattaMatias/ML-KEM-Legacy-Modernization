# Stage 1: Build C dependencies
FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# This triggers the automatic download and compilation of the liboqs C library
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Minimal Production Image
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y libssl-dev curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN apt-get update && apt-get install -y git cmake build-essential
RUN pip install --no-cache /wheels/*

COPY simulation_engine.py .
COPY tests/ tests/

EXPOSE 8080

# Production ASGI server
CMD ["uvicorn", "simulation_engine:app", "--host", "0.0.0.0", "--port", "8080"]