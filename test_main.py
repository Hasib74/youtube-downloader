import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from main import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_video_info():
    return {
        'title': 'Test Video Title',
        'id': 'test_id_123',
        'duration': 180,
        'duration_str': '03:00',
        'thumbnail': 'https://example.com/thumb.jpg',
        'uploader': 'Test Channel',
        'view_count': 1000000,
        'formats': {
            'combined': [
                {
                    'format_id': '18',
                    'ext': 'mp4',
                    'resolution': '360p',
                    'filesize': 15000000,
                    'filesize_str': '14.3 MB',
                    'fps': 30,
                    'tbr': 500,
                    'note': 'medium'
                }
            ],
            'video_only': [],
            'audio_only': [
                {
                    'format_id': '140',
                    'ext': 'm4a',
                    'resolution': 'audio only',
                    'filesize': 2500000,
                    'filesize_str': '2.4 MB',
                    'fps': None,
                    'tbr': 128,
                    'note': 'low',
                    'abr': 128
                }
            ]
        }
    }

def test_serve_frontend(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"StreamVault" in response.data or b"YouTube Video Downloader API" in response.data

@patch('main.YouTubeDownloader.get_video_info')
def test_get_info_success(mock_get_info, client, mock_video_info):
    mock_get_info.return_value = mock_video_info
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.get(f"/api/info?url={url}")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Test Video Title'
    assert data['id'] == 'test_id_123'
    assert len(data['formats']['combined']) == 1
    mock_get_info.assert_called_once_with(url)

def test_get_info_empty_url(client):
    response = client.get("/api/info?url=   ")
    assert response.status_code == 400
    assert response.get_json()["detail"] == "URL parameter cannot be empty."

@patch('main.YouTubeDownloader.get_video_info')
def test_get_info_failure(mock_get_info, client):
    mock_get_info.side_effect = ValueError("Could not retrieve video information.")
    
    response = client.get("/api/info?url=https://invalid-url.com")
    
    assert response.status_code == 400
    assert "Could not retrieve video information" in response.get_json()["detail"]

@patch('main.YouTubeDownloader.download_format')
def test_download_video_success(mock_download_format, client):
    # Create a dummy temporary file to be served
    temp_dir = tempfile.gettempdir()
    dummy_filepath = os.path.join(temp_dir, "ytdl_dummy_test.mp4")
    with open(dummy_filepath, "wb") as f:
        f.write(b"dummy video content")
        
    mock_download_format.return_value = (dummy_filepath, "test_video.mp4")
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    format_id = "18"
    
    response = client.get(f"/api/download?url={url}&format_id={format_id}")
    
    assert response.status_code == 200
    assert response.data == b"dummy video content"
    assert "content-disposition" in response.headers
    assert 'filename="test_video.mp4"' in response.headers["content-disposition"]
    
    mock_download_format.assert_called_once_with(url, format_id)
    
    # Verify the temporary file is deleted by the generator's finally block after streaming.
    assert not os.path.exists(dummy_filepath)

def test_download_video_missing_params(client):
    response = client.get("/api/download?url=https://youtube.com/watch&format_id=")
    assert response.status_code == 400
    
    response = client.get("/api/download?url=&format_id=18")
    assert response.status_code == 400

# Tests for the new Flask endpoints requested by the user

@patch('main.YouTubeDownloader.get_video_info_simple')
def test_post_video_info_success(mock_get_simple, client):
    mock_get_simple.return_value = {
        "title": "Test Video",
        "author": "Test Author",
        "length": 180,
        "views": 1000,
        "description": "Test Desc",
        "publish_date": "2026-06-22"
    }
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.post("/video_info", json={"url": url})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Test Video"
    assert data["author"] == "Test Author"
    mock_get_simple.assert_called_once_with(url)

def test_post_video_info_missing_url(client):
    response = client.post("/video_info", json={})
    assert response.status_code == 400
    assert "Missing 'url' parameter" in response.get_json()["error"]

def test_post_video_info_invalid_url(client):
    response = client.post("/video_info", json={"url": "http://invalid-url"})
    assert response.status_code == 400
    assert "Invalid YouTube URL" in response.get_json()["error"]

@patch('main.YouTubeDownloader.get_available_resolutions')
def test_post_available_resolutions_success(mock_get_resolutions, client):
    mock_get_resolutions.return_value = {
        "progressive": ["360p", "720p"],
        "all": ["360p", "720p", "1080p"]
    }
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.post("/available_resolutions", json={"url": url})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["progressive"] == ["360p", "720p"]
    assert data["all"] == ["360p", "720p", "1080p"]
    mock_get_resolutions.assert_called_once_with(url)

@patch('main.YouTubeDownloader.download_by_resolution')
def test_post_download_by_resolution_success(mock_download_by_res, client):
    mock_download_by_res.return_value = (True, None)
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.post("/download/1080p", json={"url": url})
    
    assert response.status_code == 200
    data = response.get_json()
    assert "downloaded successfully" in data["message"]
    # Verify parameter passing
    mock_download_by_res.assert_called_once()

@patch('main.YouTubeDownloader.get_format_url')
@patch('urllib.request.urlopen')
def test_download_video_stream_success(mock_urlopen, mock_get_format_url, client):
    mock_get_format_url.return_value = ("https://direct-url.com", "stream_video.mp4", {"User-Agent": "test-agent"})
    
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    
    mock_info = MagicMock()
    mock_info.get.side_effect = lambda key, default=None: {
        "Content-Length": "100",
        "Content-Type": "video/mp4"
    }.get(key, default)
    mock_response.info.return_value = mock_info
    
    mock_response.read.side_effect = [b"chunk1", b"chunk2", b""]
    mock_urlopen.return_value = mock_response
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    format_id = "18"
    
    response = client.get(f"/api/download?url={url}&format_id={format_id}&stream=true")
    
    assert response.status_code == 200
    assert response.data == b"chunk1chunk2"
    assert response.headers["Content-Length"] == "100"
    assert response.headers["Content-Type"] == "video/mp4"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert "filename*=UTF-8''stream_video.mp4" in response.headers["content-disposition"]
    
    mock_get_format_url.assert_called_once_with(url, format_id)
    mock_urlopen.assert_called_once()

@patch('main.YouTubeDownloader.get_format_url')
@patch('urllib.request.urlopen')
def test_download_video_stream_range_success(mock_urlopen, mock_get_format_url, client):
    mock_get_format_url.return_value = ("https://direct-url.com", "stream_video.mp4", {"User-Agent": "test-agent"})
    
    mock_response = MagicMock()
    mock_response.getcode.return_value = 206
    
    mock_info = MagicMock()
    mock_info.get.side_effect = lambda key, default=None: {
        "Content-Length": "50",
        "Content-Range": "bytes 0-49/100",
        "Content-Type": "video/mp4"
    }.get(key, default)
    mock_response.info.return_value = mock_info
    
    mock_response.read.side_effect = [b"chunk_partial", b""]
    mock_urlopen.return_value = mock_response
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    format_id = "18"
    
    response = client.get(
        f"/api/download?url={url}&format_id={format_id}&stream=true",
        headers={"Range": "bytes=0-49"}
    )
    
    assert response.status_code == 206
    assert response.data == b"chunk_partial"
    assert response.headers["Content-Length"] == "50"
    assert response.headers["Content-Range"] == "bytes 0-49/100"
    assert response.headers["Content-Type"] == "video/mp4"
    
    mock_urlopen.assert_called_once()
    called_args = mock_urlopen.call_args[0][0]
    assert called_args.headers["Range"] == "bytes=0-49"

@patch('yt_dlp.YoutubeDL')
def test_safe_extract_info_fallback(mock_ytdl_class):
    from downloader import YouTubeDownloader
    
    # Setup mock instances for first try (failure) and second try (success)
    mock_instance_first = MagicMock()
    mock_instance_first.__enter__.return_value.extract_info.side_effect = Exception("Requested format is not available. Use --list-formats for a list of available formats")
    
    mock_instance_second = MagicMock()
    mock_instance_second.__enter__.return_value.extract_info.return_value = {"formats": [{"format_id": "18", "ext": "mp4", "vcodec": "avc", "acodec": "mp4a"}]}
    
    mock_ytdl_class.side_effect = [mock_instance_first, mock_instance_second]
    
    url = "https://www.youtube.com/watch?v=UlacMvx_VYk"
    info = YouTubeDownloader._safe_extract_info(url)
    
    assert info["formats"][0]["format_id"] == "18"
    assert mock_ytdl_class.call_count == 2

@patch('yt_dlp.YoutubeDL')
@patch('downloader.get_cookie_file')
def test_safe_extract_info_fallback_toggle_add(mock_get_cookie_file, mock_ytdl_class):
    from downloader import YouTubeDownloader
    
    mock_get_cookie_file.return_value = "/mock/path/cookies.txt"
    
    mock_instance_first = MagicMock()
    mock_instance_first.__enter__.return_value.extract_info.side_effect = Exception("Requested format is not available")
    
    mock_instance_second = MagicMock()
    mock_instance_second.__enter__.return_value.extract_info.return_value = {"formats": [{"format_id": "18", "ext": "mp4", "vcodec": "avc", "acodec": "mp4a"}]}
    
    mock_ytdl_class.side_effect = [mock_instance_first, mock_instance_second]
    
    url = "https://www.youtube.com/watch?v=UlacMvx_VYk"
    info = YouTubeDownloader._safe_extract_info(url)
    
    assert info["formats"][0]["format_id"] == "18"
    assert mock_ytdl_class.call_count == 2
    
    first_call_opts = mock_ytdl_class.call_args_list[0][0][0]
    second_call_opts = mock_ytdl_class.call_args_list[1][0][0]
    
    assert 'player_client' not in first_call_opts.get('extractor_args', {}).get('youtube', {})
    assert second_call_opts.get('extractor_args', {}).get('youtube', {}).get('player_client') == ['android', 'ios', 'web', 'mweb']
    
    assert first_call_opts.get('cookiefile') == "/mock/path/cookies.txt"
    assert 'cookiefile' not in second_call_opts
