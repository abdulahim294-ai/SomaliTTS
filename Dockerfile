FROM python:3.11-slim

# --------------------------------------------------
# Runtime environment
# --------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --------------------------------------------------
# Install FFmpeg
# --------------------------------------------------

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && ffmpeg -version \
    && ffprobe -version \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------
# Install Python dependencies
# --------------------------------------------------

COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------
# Copy application
# --------------------------------------------------

COPY . .

# --------------------------------------------------
# Runtime user
# --------------------------------------------------

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

# --------------------------------------------------
# Application
# --------------------------------------------------

EXPOSE 10000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
