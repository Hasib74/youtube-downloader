import os
import re
import logging
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from downloader import YouTubeDownloader

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for public deployment

# Ensure downloads and static directories exist
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Helper function to check valid YouTube URL
def is_valid_youtube_url(url):
    if not url:
        return False
    # Matches: youtube.com/watch?v=..., youtu.be/..., youtube.com/shorts/..., youtube.com/embed/..., m.youtube.com/...
    pattern = r"^(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be)/(watch\?v=|shorts/|embed/)?[\w-]+(&\S*)?$"
    return re.match(pattern, url.strip()) is not None

# Flask equivalent of GET /
@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')

# Flask equivalent of GET /static/<path:path>
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# User's requested route: POST /video_info
@app.route('/video_info', methods=['POST'])
def video_info():
    data = request.get_json() or {}
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    try:
        info = YouTubeDownloader.get_video_info_simple(url)
        return jsonify(info), 200
    except Exception as e:
        logger.error(f"Error in /video_info: {e}")
        return jsonify({"error": str(e)}), 500

# User's requested route: POST /available_resolutions
@app.route('/available_resolutions', methods=['POST'])
def available_resolutions():
    data = request.get_json() or {}
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    try:
        resolutions = YouTubeDownloader.get_available_resolutions(url)
        return jsonify(resolutions), 200
    except Exception as e:
        logger.error(f"Error in /available_resolutions: {e}")
        return jsonify({"error": str(e)}), 500

# User's requested route: POST /download/<resolution>
@app.route('/download/<resolution>', methods=['POST'])
def download_by_resolution(resolution):
    data = request.get_json() or {}
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    try:
        # Download on the server in `./downloads/{video_id}`
        success, error_message = YouTubeDownloader.download_by_resolution(url, resolution, DOWNLOADS_DIR)
        if success:
            return jsonify({"message": f"Video with resolution {resolution} downloaded successfully."}), 200
        else:
            return jsonify({"error": error_message}), 500
    except Exception as e:
        logger.error(f"Error in /download/<resolution>: {e}")
        return jsonify({"error": str(e)}), 500

# Frontend compatibility route: GET /api/info
@app.route('/api/info', methods=['GET'])
def api_info():
    url = request.args.get('url')
    if not url or not url.strip():
        return jsonify({"detail": "URL parameter cannot be empty."}), 400
    
    try:
        info = YouTubeDownloader.get_video_info(url)
        return jsonify(info), 200
    except ValueError as ve:
        return jsonify({"detail": str(ve)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in /api/info: {e}")
        return jsonify({"detail": f"An error occurred while fetching video info: {str(e)}"}), 500

# Frontend compatibility route: GET /api/download
@app.route('/api/download', methods=['GET'])
def api_download():
    url = request.args.get('url')
    format_id = request.args.get('format_id')
    
    if not url or not url.strip() or not format_id or not format_id.strip():
        return jsonify({"detail": "URL and format_id parameters are required."}), 400
    
    try:
        filepath, filename = YouTubeDownloader.download_format(url, format_id)
        
        # Generator that streams file and then deletes it
        def generate():
            try:
                with open(filepath, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
            finally:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Successfully cleaned up temporary file: {filepath}")
                except Exception as e:
                    logger.error(f"Error deleting file {filepath}: {e}")
        
        response = app.response_class(
            generate(),
            mimetype="application/octet-stream"
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response
    except ValueError as ve:
        return jsonify({"detail": str(ve)}), 400
    except FileNotFoundError as fnf:
        return jsonify({"detail": str(fnf)}), 404
    except Exception as e:
        logger.error(f"Unexpected error in /api/download: {e}")
        return jsonify({"detail": f"An error occurred during the download: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8000)
