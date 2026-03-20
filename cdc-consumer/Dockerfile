FROM python:3.9-slim

WORKDIR /app

# Install curl for searching/healthchecks if needed
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the checkpoint file exists
RUN touch lsn_checkpoint.txt

CMD ["python", "main.py"]
