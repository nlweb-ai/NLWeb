# Installing Qdrant Locally on Windows

To install Qdrant on your local Windows machine, follow these steps:

---

## 1. Using Docker (Recommended)

Qdrant provides an official Docker image, which is the easiest and most portable way to run it locally.

**Steps:**

1. **Install Docker Desktop for Windows**  
   Download and install from: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

2. **Pull and run the Qdrant image**  
   Open PowerShell or Command Prompt and run:
   ```sh
   docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
   ```
   This will pull the image (if not already present) and start Qdrant, making its REST API available at [http://localhost:6333](http://localhost:6333).

---

## 2. Native Installation (via pre-built binary)

Qdrant does not officially support Windows-native binaries, but you can use Windows Subsystem for Linux (WSL) to run the Linux version on Windows.

**Steps:**

1. **Install WSL and Ubuntu (if not already installed):**
   - Open PowerShell as administrator and run:
     ```sh
     wsl --install
     ```
   - Restart your computer if prompted.

2. **Open Ubuntu terminal and run:**
   ```sh
   curl -O https://releases.qdrant.tech/v1.9.2/qdrant-x86_64-unknown-linux-gnu.tar.gz
   tar -xzf qdrant-x86_64-unknown-linux-gnu.tar.gz
   cd qdrant-x86_64-unknown-linux-gnu
   ./qdrant
   ```
   This will start Qdrant on the default port.

---

## 3. For Python Projects (Client Only)

If you just need to interact with Qdrant from Python (not run the server), install the client:

```sh
pip install qdrant-client
```

But you still need a running Qdrant server (Docker or WSL methods above).

---

## Summary (Best for NLWeb)

- **Use Docker for easiest setup on Windows.**
- Access Qdrant at [http://localhost:6333](http://localhost:6333) after starting the container.