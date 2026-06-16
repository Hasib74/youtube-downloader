# StreamVault - Premium YouTube Downloader & API

StreamVault is a production-ready Web API and client application for downloading YouTube videos and audio. Built with Python using **FastAPI** and **yt-dlp**, it serves a sleek, responsive dark-mode dashboard styled with modern glassmorphism aesthetics.

Designed for public deployment, the application handles downloads securely by streaming files through the server to bypass IP restrictions, and automatically cleans up temporary server files after serving the user.

---

## Features

- **Video Info Analysis**: Fetches titles, durations, channels, views, and thumbnails dynamically.
- **Grouped Formats**: Automatically categorizes available downloads into:
  - **Video + Audio (Combined)**: Pre-merged streams for immediate download.
  - **Video Only**: High-resolution video streams.
  - **Audio Only**: Extract audio tracks (e.g., MP3/M4A) at various bitrates.
- **Safe Server Cleanup**: Downloads files to local temp directories, streams them to the browser as a binary file response, and immediately cleans them up via FastAPI background tasks.
- **Glassmorphism UI**: Beautiful, interactive web interface featuring smooth micro-animations, loading indicators, custom download states, and responsive grids.
- **Fully Documented API**: Automated API documentation served by FastAPI Swagger.

---

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, Uvicorn, yt-dlp
- **Frontend**: HTML5, Vanilla CSS3 (Custom Variables, Flexbox/Grid, Keyframe Animations), Vanilla JavaScript (fetch API, Blobs)
- **Testing**: Pytest, FastAPI TestClient

---

## Prerequisites

For the most basic download functionality, only Python is required. However, **`ffmpeg` is highly recommended**. If installed on the system, `yt-dlp` will automatically use it to merge high-definition video-only formats with their audio tracks.

### Installing FFmpeg

- **macOS** (via Homebrew):
  ```bash
  brew install ffmpeg
  ```
- **Debian / Ubuntu**:
  ```bash
  sudo apt update
  sudo apt install ffmpeg
  ```
- **Windows** (via Chocolatey):
  ```cmd
  choco install ffmpeg
  ```

---

## Getting Started

### 1. Clone & Navigate
Navigate to the directory:
```bash
cd youtube-downloader
```

### 2. Create Virtual Environment
Create and activate a Python virtual environment:
```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
Install packages listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Run the Dev Server
Start the FastAPI server using Uvicorn:
```bash
uvicorn main:app --reload
```
The application will be running at **`http://localhost:8000`**.

---

## Running Automated Tests

Run the test suite using `pytest`:
```bash
pytest test_main.py
```

---

## API Documentation

Once the server is running, you can explore the endpoints and test them directly from your browser using Swagger:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints

#### `GET /api/info`
Extracts metadata and format options for a YouTube video.
- **Query Parameter**: `url` (string, required)
- **Response**: JSON structure including title, author, views, duration, and lists of formats grouped by type.

#### `GET /api/download`
Downloads a video and streams it to the user.
- **Query Parameters**:
  - `url` (string, required)
  - `format_id` (string, required)
- **Response**: File stream (`application/octet-stream`) with `Content-Disposition` attachment headers triggering local download.

---

## Public Deployment Guide

This app is built to be deployed on hosting providers (e.g. Render, Heroku, Railway, or VPS).

### 1. Render Deployment
1. Create a new **Web Service** on Render pointing to your repository.
2. Select **Python** environment.
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add the **FFmpeg buildpack** or install via Render's Docker environments to enable high-quality video merging.

### 2. Docker Deployment
You can also package this application as a Docker container. Create a `Dockerfile`:
```dockerfile
FROM python:3.10-slim

# Install system dependencies (including ffmpeg)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Build and run:
```bash
docker build -t youtube-downloader .
docker run -p 8000:8000 youtube-downloader
```
