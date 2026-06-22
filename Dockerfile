FROM python:3.12.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=prod
ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=5000
ENV WEB_THREADS=8
ENV UPLOAD_FOLDER=/app/uploads
ENV DATABASE_PATH=/app/data/database.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/data

EXPOSE 5000

CMD ["python", "scripts/run_waitress.py"]
