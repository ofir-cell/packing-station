FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FRAMES_DIR=/data/frames LIVEVISION_DB=/data/livevision.db
EXPOSE 8080
CMD gunicorn -w 1 --threads 8 -b 0.0.0.0:${PORT:-8080} app:app
