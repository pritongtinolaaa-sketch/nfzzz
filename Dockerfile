# Use a Debian-based Python image (compatible with Playwright deps)
FROM python:3.12-slim-bookworm

# Install required system libraries for Chromium/Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    fonts-liberation \
    libappindicator3-1 \
    libnspr4 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Copy & install Python deps first (caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (deps already present, so no sudo issues)
RUN playwright install chromium

# Copy rest of app
COPY . .

# Railway uses $PORT env var automatically
ENV PORT=8080

# Start Gunicorn (timeout 120s for slow recovery)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--timeout", "120", "--log-level", "info"]
