import threading
import time
import random
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

class CloudService:
    """
    Tier 3: The Cloud Backend.
    Holds its own private key. Exposes its public key to authorized gateways.
    Responsible for alerting on medicine threshold breaches.
    """
    def __init__(self):
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()
        print("[CLOUD] Initialized. RSA Keypair generated.")

    def receive_data(self, encrypted_data):
        # Decrypt using Cloud's Private Key
        decrypted = self.private_key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
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
    Tier 2: Local Edge Gateway (e.g., Raspberry Pi on the facility network).
    Decrypts local device traffic, sanitizes/batches it, and encrypts for the WAN.
    """
    def __init__(self, cloud_service):
        self.cloud = cloud_service
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()
        print("[GATEWAY] Initialized. RSA Keypair generated. Connected to Cloud.")

    def receive_from_device(self, encrypted_data):
        # 1. Decrypt payload from the local device
        decrypted = self.private_key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        temp_str = decrypted.decode('utf-8')
        print(f"[GATEWAY] Decrypted local payload: {temp_str}°C. Re-encrypting for WAN over to Cloud...")

        # 2. Re-encrypt the payload using the Cloud's public key
        encrypted_for_cloud = self.cloud.public_key.encrypt(
            temp_str.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # 3. Forward over simulated WAN
        self.cloud.receive_data(encrypted_for_cloud)


class LegacyDevice(threading.Thread):
    """
    Tier 1: Simulated Arduino Sensor.
    Has limited compute. Only knows the Gateway's public key.
    """
    def __init__(self, gateway):
        super().__init__()
        self.gateway = gateway
        self.running = True

    def run(self):
        print("[DEVICE] Booting simulated legacy sensor...\n")
        while self.running:
            # Simulate mostly stable temps (2 to 6C) with occasional critical spikes
            if random.random() > 0.85:
                temp = random.uniform(-2.0, 11.0) # Anomaly
            else:
                temp = random.uniform(2.0, 6.0)   # Nominal

            payload = f"{temp:.2f}".encode('utf-8')

            # Encrypt payload using Gateway's public key
            encrypted_payload = self.gateway.public_key.encrypt(
                payload,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            print(f"[DEVICE] Read {temp:.2f}°C. Ciphertext generated. Transmitting...")
            self.gateway.receive_from_device(encrypted_payload)
            
            # Poll every 3 seconds
            time.sleep(10)

if __name__ == "__main__":
    # Boot the infrastructure
    cloud = CloudService()
    gateway = EdgeGateway(cloud)
    
    # Boot the edge device and start the simulation loop
    device = LegacyDevice(gateway)
    device.start()

    try:
        # Keep main thread alive while daemon threads run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down simulation...")
        device.running = False
        device.join()
