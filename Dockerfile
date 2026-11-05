FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 実曲用のボーカル分離（Demucs）。イメージが約2GB増えるので、使う時だけ: docker compose build --build-arg WITH_DEMUCS=1
ARG WITH_DEMUCS=0
RUN if [ "$WITH_DEMUCS" = "1" ]; then pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir demucs; fi
COPY transcribe.py ./
COPY server ./server
COPY web ./web
ENV FREE_PER_DAY=3
EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
