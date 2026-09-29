FROM python:3.11-slim

WORKDIR /app

# System dependencies (OpenCV runtime, zbar, curl for healthcheck)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libzbar0 \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Google Chrome (required by Selenium client for QR visual channel)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN useradd -m -u 1000 recon && chown -R recon /app
USER recon

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD python -c "import requests; requests.get('http://localhost:8443/check', timeout=3)" \
    || exit 1

CMD ["python", "c2_server.py"]