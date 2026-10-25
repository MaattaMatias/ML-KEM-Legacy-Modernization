# ML-KEM-Legacy-Modernization

This program simulates a fridge sensor, a gateway, and a cloud API on your own computer. The sensor sends a temperature about every 10 seconds. The gateway encrypts it with ML-KEM and posts it to the API at `http://127.0.0.1:8080`.

## What you need

- Python 3.11
- Git, CMake, Ninja, a C compiler, and OpenSSL

`liboqs-python` compiles a native library the first time you install or import it. That step needs the tools above, and it can take several minutes.

On Ubuntu or Debian:

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv cmake build-essential ninja-build git libssl-dev
```

On Windows, install [Python 3.11](https://www.python.org/downloads/), [Git](https://git-scm.com/), [CMake](https://cmake.org/download/), and [Ninja](https://ninja-build.org/), and add them to your PATH. Install Visual Studio Build Tools and select the **Desktop development with C++** workload. Install the Win64 OpenSSL build from [slproweb.com](https://slproweb.com/products/Win32OpenSSL.html), then point the build at it before installing Python packages:

```powershell
$env:OPENSSL_ROOT_DIR = "C:\Program Files\OpenSSL-Win64"
```

Use the folder where OpenSSL was installed if it differs from that path.

## Install

Open a terminal in this folder.

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS or Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

With the virtual environment still active:

```bash
python simulation_engine.py
```

Leave that window open. The program prints when the API is online, when the gateway has the public key, and when each temperature is sent. Readings inside 0–8°C are logged as nominal. Readings outside that range are logged as alerts.

While it is running, open `http://127.0.0.1:8080/healthz` in a browser. A response of `{"status":"alive"}` means the API is up. Interactive API docs are at `http://127.0.0.1:8080/docs`.

Port 8080 must be free before you start.

## Stop

Press `Ctrl+C` in the terminal. The program shuts down the simulated device and exits.
