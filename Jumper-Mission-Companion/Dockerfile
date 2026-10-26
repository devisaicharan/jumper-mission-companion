FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    UPSTREAM_DIR=/opt/jumper-upstream NATIVE_MODEL_CACHE=/opt/jumper-model-cache \
    MISSION_BACKEND=native MAX_SESSIONS=1 PORT=10000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libstdc++6 libgomp1 libgl1 libegl1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-cloud.txt ./
RUN python -m pip install --no-cache-dir -r requirements-cloud.txt
COPY . .
RUN python tools/fetch_upstream.py && python tools/native_preflight.py --build-model-cache \
    && python tools/native_preflight.py
RUN useradd --uid 10001 --create-home companion
USER companion
EXPOSE 10000
CMD ["python", "cloud_start.py"]
