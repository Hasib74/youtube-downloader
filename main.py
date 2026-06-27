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

# Debug route to inspect environment variables and yt-dlp version on the server
@app.route('/api/debug', methods=['GET'])
def api_debug():
    import sys
    import yt_dlp
    import shutil
    
    yt_cookies_env = os.environ.get("YT_COOKIES")
    cookie_info = "Not Set"
    if yt_cookies_env:
        lines = yt_cookies_env.splitlines()
        cookie_info = {
            "exists": True,
            "length": len(yt_cookies_env),
            "line_count": len(lines),
            "starts_with": yt_cookies_env[:30] if len(yt_cookies_env) > 0 else "",
            "contains_tabs": "\t" in yt_cookies_env,
            "contains_spaces": "  " in yt_cookies_env,
        }
        
    local_cookies_exists = os.path.exists(os.path.join(os.path.dirname(__file__), "cookies.txt"))
    cookie_diagnostics = YouTubeDownloader.check_cookies_status()
    
    return jsonify({
        "python_version": sys.version,
        "yt_dlp_version": yt_dlp.version.__version__,
        "ffmpeg_available": shutil.which('ffmpeg') is not None or shutil.which('ffprobe') is not None,
        "node_available": shutil.which('node') is not None,
        "nodejs_available": shutil.which('nodejs') is not None,
        "deno_available": shutil.which('deno') is not None,
        "YT_COOKIES": cookie_info,
        "local_cookies_txt_exists": local_cookies_exists,
        "cookie_diagnostics": cookie_diagnostics,
        "YT_PO_TOKEN_exists": os.environ.get("YT_PO_TOKEN") is not None,
        "YT_VISITOR_DATA_exists": os.environ.get("YT_VISITOR_DATA") is not None,
        "YT_PROXY_exists": os.environ.get("YT_PROXY") is not None,
    }), 200

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
    stream_param = request.args.get('stream', 'false').lower() == 'true'
    
    if not url or not url.strip() or not format_id or not format_id.strip():
        return jsonify({"detail": "URL and format_id parameters are required."}), 400
    
    if stream_param:
        try:
            direct_url, filename, yt_headers = YouTubeDownloader.get_format_url(url, format_id)
            
            import urllib.request
            import urllib.error
            
            headers = dict(yt_headers)
            headers.pop('Host', None)
            headers.pop('host', None)
            
            cookies_dict = YouTubeDownloader.get_cookies_dict()
            if cookies_dict:
                user_agent = headers.get("User-Agent", headers.get("user-agent", ""))
                if "Mozilla" in user_agent or "Safari" in user_agent or "Chrome" in user_agent:
                    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())
                    headers["Cookie"] = cookie_str

            range_header = request.headers.get('Range')
            if range_header:
                headers["Range"] = range_header
                logger.info(f"Forwarding client Range header: {range_header}")

            req = urllib.request.Request(direct_url, headers=headers)
            try:
                r = urllib.request.urlopen(req)
            except urllib.error.HTTPError as he:
                logger.error(f"urllib stream request failed: {he.code} - {he.reason}")
                return jsonify({"detail": f"YouTube stream request failed: {he.code} {he.reason}"}), he.code
            
            status_code = r.getcode()
            content_length = r.info().get("Content-Length")
            content_range = r.info().get("Content-Range")
            content_type = r.info().get("Content-Type", "application/octet-stream")

            def generate_stream():
                try:
                    while True:
                        chunk = r.read(16384)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    r.close()
            
            import urllib.parse
            quoted_filename = urllib.parse.quote(filename)
            ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
            if not ascii_filename.strip():
                ascii_filename = "download"

            response = app.response_class(
                generate_stream(),
                status=status_code,
                mimetype=content_type
            )
            response.headers["Content-Disposition"] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quoted_filename}'
            response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
            response.headers["Accept-Ranges"] = "bytes"
            
            if content_length:
                response.headers["Content-Length"] = content_length
            if content_range:
                response.headers["Content-Range"] = content_range
                
            return response
        except ValueError as ve:
            return jsonify({"detail": str(ve)}), 400
        except Exception as e:
            logger.error(f"Unexpected error in stream proxy: {e}")
            return jsonify({"detail": f"An error occurred during direct streaming: {str(e)}"}), 500

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
        
        import urllib.parse
        quoted_filename = urllib.parse.quote(filename)
        ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
        if not ascii_filename.strip():
            ascii_filename = "download"

        response = app.response_class(
            generate(),
            mimetype="application/octet-stream"
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quoted_filename}'
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response
    except ValueError as ve:
        return jsonify({"detail": str(ve)}), 400
    except FileNotFoundError as fnf:
        return jsonify({"detail": str(fnf)}), 404
    except Exception as e:
        logger.error(f"Unexpected error in /api/download: {e}")
        return jsonify({"detail": f"An error occurred during the download: {str(e)}"}), 500

@app.route('/api/test-extraction', methods=['GET'])
def api_test_extraction():
    url = request.args.get('url', 'https://www.youtube.com/watch?v=zQl7zYkEP6M')
    client = request.args.get('client', 'android')
    
    import yt_dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': False,
        'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': [client]}},
    }
    import shutil
    node_path = shutil.which('node') or shutil.which('nodejs')
    if node_path:
        ydl_opts['js_runtimes'] = {'node': {'path': node_path}}
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"status": "success", "formats_count": len(info.get('formats', []))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "node_path": node_path})

@app.route('/api/test-verbose', methods=['GET'])
def api_test_verbose():
    url = request.args.get('url', 'https://www.youtube.com/watch?v=UlacMvx_VYk')
    import subprocess
    import sys
    
    cmd = [sys.executable, "-m", "yt_dlp", "-v", url]
    
    # Check if local cookies exist
    local_cookies = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.exists(local_cookies):
        cmd.extend(["--cookiefile", local_cookies])
        
    proxy = os.environ.get("YT_PROXY")
    if proxy:
        cmd.extend(["--proxy", proxy])
        
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        return jsonify({
            "stdout": res.stdout,
            "stderr": res.stderr,
            "returncode": res.returncode,
            "cmd": cmd
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=False, host="0.0.0.0", port=port)

