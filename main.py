import os
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from downloader import YouTubeDownloader

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Video Downloader API",
    description="A robust FastAPI backend for downloading YouTube videos and audio files.",
    version="1.0.0"
)

# Enable CORS for public deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper function to delete temporary files after serving them
def cleanup_temp_file(filepath: str):
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Successfully cleaned up temporary file: {filepath}")
    except Exception as e:
        logger.error(f"Error deleting file {filepath}: {e}")

@app.get("/api/info")
async def get_info(url: str = Query(..., description="The YouTube video URL")):
    if not url.strip():
        raise HTTPException(status_code=400, detail="URL parameter cannot be empty.")
    try:
        info = YouTubeDownloader.get_video_info(url)
        return info
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error in /api/info: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching video info: {str(e)}")

@app.get("/api/download")
async def download_video(
    url: str = Query(..., description="The YouTube video URL"),
    format_id: str = Query(..., description="The specific format ID to download"),
    background_tasks: BackgroundTasks = None
):
    if not url.strip() or not format_id.strip():
        raise HTTPException(status_code=400, detail="URL and format_id parameters are required.")
    
    try:
        filepath, filename = YouTubeDownloader.download_format(url, format_id)
        
        # Schedule the file to be deleted once the response has been sent
        if background_tasks:
            background_tasks.add_task(cleanup_temp_file, filepath)
        else:
            # Fallback if background_tasks is somehow missing (e.g. direct test calls)
            logger.warning("BackgroundTasks not provided, file will not be automatically deleted")
            
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/octet-stream",
            headers={"Access-Control-Expose-Headers": "Content-Disposition"}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        logger.error(f"Unexpected error in /api/download: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred during the download: {str(e)}")

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return """
    <html>
        <head>
            <title>Downloader API</title>
            <style>
                body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #121212; color: white; }
                .container { text-align: center; border: 1px solid #333; padding: 40px; border-radius: 8px; background-color: #1e1e1e; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>YouTube Video Downloader API</h1>
                <p>Backend is running successfully!</p>
                <p>Frontend static files (static/index.html) are not yet generated.</p>
            </div>
        </body>
    </html>
    """
