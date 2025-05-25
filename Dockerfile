FROM python:3.10-slim

# Install system dependencies to support builds
RUN apt-get update && apt-get install -y \
    build-essential gcc libffi-dev libssl-dev \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "app/example.py"]

