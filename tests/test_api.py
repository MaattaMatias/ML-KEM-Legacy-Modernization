import os
import oqs
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

# Import the FastAPI app and the Public Key from the integrated simulation engine
from simulation_engine import app, CLOUD_PUBLIC_KEY

client = TestClient(app)

def test_health_probe():
    """Test that the liveness probe responds successfully."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

def test_readiness_probe():
    """Test that the crypto readiness probe responds successfully."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_public_key_endpoint():
    """Test that the Gateway can fetch the Post-Quantum public key."""
    response = client.get("/public-key")
    assert response.status_code == 200
    assert "public_key" in response.json()
    
    # Ensure the key returned matches the one held in memory
    assert response.json()["public_key"] == CLOUD_PUBLIC_KEY.hex()

def test_secure_telemetry_flow():
    """Test the end-to-end Gateway-to-Cloud hybrid encryption flow."""
    # 1. Gateway encapsulates against the Cloud's public key
    kem_client = oqs.KeyEncapsulation("ML-KEM-1024")
    encapsulated_key, shared_secret = kem_client.encap_secret(CLOUD_PUBLIC_KEY)
    
    # 2. Gateway encrypts temperature payload using the shared secret
    aesgcm = AESGCM(shared_secret)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, b"5.5", None)
    
    # 3. Simulate Gateway transmitting to Cloud via HTTP POST
    response = client.post("/telemetry", json={
        "encapsulated_key": encapsulated_key.hex(),
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex()
    })
    
    # 4. Assert the Cloud successfully decapsulated and decrypted the payload
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

def test_invalid_telemetry_flow():
    """Test that tampered ciphertext is rejected by AES-GCM auth tags."""
    kem_client = oqs.KeyEncapsulation("ML-KEM-1024")
    encapsulated_key, shared_secret = kem_client.encap_secret(CLOUD_PUBLIC_KEY)
    
    aesgcm = AESGCM(shared_secret)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, b"5.5", None)
    
    # Tamper with the ciphertext (flip a bit)
    tampered_ciphertext = bytearray(ciphertext)
    tampered_ciphertext[0] ^= 0xFF
    
    response = client.post("/telemetry", json={
        "encapsulated_key": encapsulated_key.hex(),
        "nonce": nonce.hex(),
        "ciphertext": tampered_ciphertext.hex()
    })
    
    # Should throw a 400 Bad Request because AES-GCM decryption failed
    assert response.status_code == 400
    assert response.json() == {"detail": "Decryption failed"}