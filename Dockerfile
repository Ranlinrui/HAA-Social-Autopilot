FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and Chromium for BrowserEngine
RUN apt-get update && apt-get install -y \
    gcc \
    chromium \
    fonts-liberation \
    fluxbox \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    novnc \
    websockify \
    x11vnc \
    xvfb \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app ./app
COPY backend/scripts/start-backend.sh /app/start-backend.sh

# Create directories
RUN chmod +x /app/start-backend.sh && mkdir -p uploads data

EXPOSE 8000
EXPOSE 6080

CMD ["/app/start-backend.sh"]
