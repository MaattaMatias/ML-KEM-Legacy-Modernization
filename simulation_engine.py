import os
import time
import random
import threading
import logging
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from pythonjsonlogger import jsonlogger
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import oqs

# ==========================================
# 1. CLOUD SERVICE (FastAPI Tier)
# ==========================================

# --- Logging & Metrics Setup ---
logger = logging.getLogger("cloud-service")
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
logHandler.setFormatter(jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logger.addHandler(logHandler)

REQUEST_COUNT = Counter('http_requests_total', 'HTTP Requests', ['method', 'endpoint', 'status'])
TELEMETRY_ALERTS = Counter('telemetry_alerts_total', 'Total critical threshold breaches')

# --- Post-Quantum Key Generation ---
kem = oqs.KeyEncapsulation("ML-KEM-1024")
CLOUD_PUBLIC_KEY = kem.generate_keypair()
CLOUD_PRIVATE_KEY = kem.export_secret_key()

app = FastAPI(title="Cloud IoT Service")

class TelemetryPayload(BaseModel):
    encapsulated_key: str
    nonce: str
    ciphertext: str

@app.get("/healthz")
def healthz():
    return {"status": "alive"}

@app.get("/ready")
def readiness_probe():
    """Confirms crypto libraries are loaded and ready to accept traffic."""
    try:
        _ = oqs.KeyEncapsulation("ML-KEM-1024")
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness check failed", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Crypto Subsystem Unavailable")

@app.get("/metrics")
def get_metrics():
    """Scraped by Prometheus (and tested by GitHub Actions)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/public-key")
def get_public_key():
    """Endpoint for Gateways to download the public key on boot."""
    return {"public_key": CLOUD_PUBLIC_KEY.hex()}

@app.post("/telemetry")
def receive_telemetry(payload: TelemetryPayload):
    try:
        encap_key = bytes.fromhex(payload.encapsulated_key)
        nonce = bytes.fromhex(payload.nonce)
        ciphertext = bytes.fromhex(payload.ciphertext)

        # 1. Decapsulate ML-KEM secret
        kem_decaps = oqs.KeyEncapsulation("ML-KEM-1024")
        kem_decaps.secret_key = CLOUD_PRIVATE_KEY
        shared_secret = kem_decaps.decap_secret(encap_key)

        # 2. Decrypt AES-256 payload
        aesgcm = AESGCM(shared_secret)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        temp = float(decrypted.decode('utf-8'))

        # 3. Evaluate Thresholds
        if temp > 8.0 or temp < 0.0:
            TELEMETRY_ALERTS.inc()
            logger.warning("🔴 CRITICAL THRESHOLD BREACH", extra={"temperature": temp, "status": "ALERT"})
        else:
            logger.info("🟢 Telemetry nominal", extra={"temperature": temp, "status": "OK"})

        return {"status": "success"}
    except Exception as e:
        logger.error("Decryption failed", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail="Decryption failed")

def run_cloud_server():
    """Runs the FastAPI server in a background thread."""
    # We suppress uvicorn logs to let our JSON logger stand out
    uvicorn.run(app, host="127.0.0.1", port=8080, log_config=None)


# ==========================================
# 2. EDGE GATEWAY (Tier 2)
# ==========================================

DEVICE_PSK = b'\x01' * 32  # 256-bit PSK for local Device -> Gateway network

class EdgeGateway:
    def __init__(self, cloud_url="http://127.0.0.1:8080"):
        self.cloud_url = cloud_url
        self.device_aes = AESGCM(DEVICE_PSK)
        
        print("[GATEWAY] Booting. Fetching Cloud's ML-KEM Public Key via HTTP...")
        # Fetch the Cloud's Public Key over HTTP
        response = requests.get(f"{self.cloud_url}/public-key")
        self.cloud_public_key = bytes.fromhex(response.json()["public_key"])
        print("[GATEWAY] ML-KEM Public Key successfully retrieved. Ready to route traffic.")

    def receive_from_device(self, payload):
        # 1. Decrypt AES-256 local traffic
        decrypted_temp = self.device_aes.decrypt(payload['nonce'], payload['ciphertext'], None)
        print(f"\n[GATEWAY] Received {decrypted_temp.decode('utf-8')}°C from device. Securing for WAN...")

        # 2. Hybrid Quantum-Safe Encapsulation & Encryption
        kem_encaps = oqs.KeyEncapsulation("ML-KEM-1024")
        encapsulated_key, shared_secret = kem_encaps.encap_secret(self.cloud_public_key)

        cloud_aes = AESGCM(shared_secret)
        cloud_nonce = os.urandom(12)
        cloud_ciphertext = cloud_aes.encrypt(cloud_nonce, decrypted_temp, None)

        # 3. HTTP POST to Cloud Service
        cloud_payload = {
            "encapsulated_key": encapsulated_key.hex(),
            "nonce": cloud_nonce.hex(),
            "ciphertext": cloud_ciphertext.hex()
        }
        
        try:
            res = requests.post(f"{self.cloud_url}/telemetry", json=cloud_payload)
            if res.status_code == 200:
                print(f"[GATEWAY] Successfully routed payload to Cloud Service via HTTP POST.")
            else:
                print(f"[GATEWAY] ERROR: Cloud returned {res.status_code}")
        except requests.exceptions.ConnectionError:
            print("[GATEWAY] ERROR: Failed to connect to Cloud Service.")


# ==========================================
# 3. LEGACY DEVICE (Tier 1)
# ==========================================

class LegacyDevice(threading.Thread):
    def __init__(self, gateway):
        super().__init__()
        self.gateway = gateway
        self.running = True
        self.aesgcm = AESGCM(DEVICE_PSK)

    def run(self):
        print("[DEVICE] Simulated Arduino booting. PSK loaded. Starting telemetry loop...")
        while self.running:
            if random.random() > 0.85:
                temp = random.uniform(-2.0, 11.0) # Anomaly
            else:
                temp = random.uniform(2.0, 6.0)   # Nominal

            payload_bytes = f"{temp:.2f}".encode('utf-8')
            nonce = os.urandom(12)
            ciphertext = self.aesgcm.encrypt(nonce, payload_bytes, None)
            
            # Send to local gateway via simulated local network (function call)
            self.gateway.receive_from_device({
                'nonce': nonce,
                'ciphertext': ciphertext
            })
            
            time.sleep(10)


# ==========================================
# ORCHESTRATION SCRIPT
# ==========================================

if __name__ == "__main__":
    # 1. Start the Cloud Service API in a daemon thread
    cloud_thread = threading.Thread(target=run_cloud_server, daemon=True)
    cloud_thread.start()

    # Wait for FastAPI to bind to the port
    print("[SYSTEM] Waiting for FastAPI Cloud Service to boot...")
    for _ in range(10):
        try:
            if requests.get("http://127.0.0.1:8080/healthz").status_code == 200:
                print("[SYSTEM] Cloud Service API is Online.\n")
                break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        print("[SYSTEM] Failed to boot Cloud Service. Exiting.")
        exit(1)

    # 2. Initialize the Edge Gateway
    gateway = EdgeGateway("http://127.0.0.1:8080")

    # 3. Start the Device Simulator
    device = LegacyDevice(gateway)
    device.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SYSTEM] Shutting down simulation...")
        device.running = False
        device.join()