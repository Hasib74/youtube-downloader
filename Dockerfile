FROM python:3.10-slim

# Install system dependencies (including ffmpeg for merging high-quality formats)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency list and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source files
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Set production environment variables
ENV PYTHONUNBUFFERED=1

# Command to run uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
