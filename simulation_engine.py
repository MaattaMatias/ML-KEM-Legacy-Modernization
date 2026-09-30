import os
import time
import random
import threading
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import oqs  # Open Quantum Safe Python Wrapper

# ---------------------------------------------------------
# Pre-Shared Key (PSK) for the local Legacy Device Network
# 32 bytes = 256-bit key for AES-256. 
# In physical deployment, this is burned into the Arduino.
# ---------------------------------------------------------
DEVICE_PSK = b'\x01' * 32 

class CloudService:
    """
    Tier 3: The Cloud Backend.
    Uses ML-KEM-1024 (Kyber) for Post-Quantum secure key exchange.
    """
    def __init__(self):
        # Generate ML-KEM-1024 Keypair
        self.kem = oqs.KeyEncapsulation("ML-KEM-1024")
        self.public_key = self.kem.generate_keypair()
        self.private_key = self.kem.export_secret_key()
        print("[CLOUD] Initialized. Post-Quantum ML-KEM-1024 Keypair generated.")

    def receive_data(self, payload):
        # Unpack the hybrid KEM payload
        encapsulated_key = payload['encapsulated_key']
        nonce = payload['nonce']
        ciphertext = payload['ciphertext']

        # 1. Decapsulate the shared secret using ML-KEM-1024 private key
        kem_decaps = oqs.KeyEncapsulation("ML-KEM-1024")
        kem_decaps.secret_key = self.private_key
        shared_secret = kem_decaps.decap_secret(encapsulated_key)

        # 2. Decrypt the telemetry using AES-256-GCM keyed by the shared secret
        # ML-KEM-1024 outputs a 32-byte secret, perfectly sized for AES-256
        aesgcm = AESGCM(shared_secret)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        
        temp = float(decrypted.decode('utf-8'))
        self.evaluate_telemetry(temp)

    def evaluate_telemetry(self, temp):
        # Alerting Logic: Medicine must remain between 0C and +8C
        if temp > 8.0 or temp < 0.0:
            print(f"\n[CLOUD ALERT] 🔴 CRITICAL THRESHOLD BREACH: {temp:.2f}°C")
            print("[CLOUD ALERT] Dispatching emergency notification to facility manager.\n")
        else:
            print(f"[CLOUD INFO] 🟢 Telemetry nominal: {temp:.2f}°C")

class EdgeGateway:
    """
    Tier 2: Local Edge Gateway.
    Bridging the local AES network to the Post-Quantum WAN.
    """
    def __init__(self, cloud_service):
        self.cloud = cloud_service
        # Initialize symmetric AES for the local network
        self.device_aes = AESGCM(DEVICE_PSK)
        print("[GATEWAY] Initialized. AES-256 Pre-Shared Key loaded. Connected to Cloud.")

    def receive_from_device(self, payload):
        # 1. Decrypt local payload using AES-256-GCM
        nonce = payload['nonce']
        ciphertext = payload['ciphertext']
        
        decrypted_temp = self.device_aes.decrypt(nonce, ciphertext, None)
        temp_str = decrypted_temp.decode('utf-8')
        print(f"[GATEWAY] Decrypted local payload: {temp_str}°C. Securing for WAN via ML-KEM 1024...")

        # 2. Post-Quantum Hybrid Encryption for WAN
        # Generate a shared secret and encapsulate it against the Cloud's public key
        kem_encaps = oqs.KeyEncapsulation("ML-KEM-1024")
        encapsulated_key, shared_secret = kem_encaps.encap_secret(self.cloud.public_key)

        # Encrypt the telemetry using the dynamically negotiated shared secret
        cloud_aes = AESGCM(shared_secret)
        cloud_nonce = os.urandom(12) # GCM requires a 12-byte nonce
        cloud_ciphertext = cloud_aes.encrypt(cloud_nonce, decrypted_temp, None)

        # 3. Forward to Cloud
        cloud_payload = {
            'encapsulated_key': encapsulated_key,
            'nonce': cloud_nonce,
            'ciphertext': cloud_ciphertext
        }
        self.cloud.receive_data(cloud_payload)


class LegacyDevice(threading.Thread):
    """
    Tier 1: Simulated Arduino Sensor.
    Stripped of RSA. Now relies on highly efficient AES-256.
    """
    def __init__(self, gateway):
        super().__init__()
        self.gateway = gateway
        self.running = True
        self.aesgcm = AESGCM(DEVICE_PSK)

    def run(self):
        print("[DEVICE] Booting simulated legacy sensor with AES-256...\n")
        while self.running:
            if random.random() > 0.85:
                temp = random.uniform(-2.0, 11.0) # Simulate anomaly
            else:
                temp = random.uniform(2.0, 6.0)   # Simulate nominal

            payload_bytes = f"{temp:.2f}".encode('utf-8')

            # Encrypt payload using Symmetric AES-256
            nonce = os.urandom(12)
            ciphertext = self.aesgcm.encrypt(nonce, payload_bytes, None)

            print(f"[DEVICE] Read {temp:.2f}°C. AES-256 payload generated. Transmitting...")
            
            self.gateway.receive_from_device({
                'nonce': nonce,
                'ciphertext': ciphertext
            })
            
            time.sleep(10)

if __name__ == "__main__":
    cloud = CloudService()
    gateway = EdgeGateway(cloud)
    
    device = LegacyDevice(gateway)
    device.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down simulation...")
        device.running = False
        device.join()