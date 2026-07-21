# Raspberry Pi / multi-arch friendly image for AlgoTrading V2
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Madrid

WORKDIR /app

# System deps: build tools for any wheels that need compiling on ARM,
# plus tzdata so Europe/Madrid is available inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libffi-dev \
        tzdata \
        curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

# Persist strategy edits / logs via compose volumes
RUN mkdir -p /app/strategies /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/strategies >/dev/null || exit 1

CMD ["uvicorn", "frontend.main:app", "--host", "0.0.0.0", "--port", "8000"]
