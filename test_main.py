import os
import tempfile
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Import app to be tested
from main import app

client = TestClient(app)

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

def test_serve_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "StreamVault" in response.text or "YouTube Video Downloader API" in response.text

@patch('main.YouTubeDownloader.get_video_info')
def test_get_info_success(mock_get_info, mock_video_info):
    mock_get_info.return_value = mock_video_info
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.get(f"/api/info?url={url}")
    
    assert response.status_code == 200
    data = response.json()
    assert data['title'] == 'Test Video Title'
    assert data['id'] == 'test_id_123'
    assert len(data['formats']['combined']) == 1
    mock_get_info.assert_called_once_with(url)

def test_get_info_empty_url():
    response = client.get("/api/info?url=   ")
    assert response.status_code == 400
    assert response.json()["detail"] == "URL parameter cannot be empty."

@patch('main.YouTubeDownloader.get_video_info')
def test_get_info_failure(mock_get_info):
    mock_get_info.side_effect = ValueError("Could not retrieve video information.")
    
    response = client.get("/api/info?url=https://invalid-url.com")
    
    assert response.status_code == 400
    assert "Could not retrieve video information" in response.json()["detail"]

@patch('main.YouTubeDownloader.download_format')
def test_download_video_success(mock_download_format):
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
    assert response.content == b"dummy video content"
    assert "content-disposition" in response.headers
    assert 'filename="test_video.mp4"' in response.headers["content-disposition"]
    
    mock_download_format.assert_called_once_with(url, format_id)
    
    # Under FastAPI's TestClient, background tasks run synchronously.
    # Therefore, the temporary file is already deleted by cleanup_temp_file.
    assert not os.path.exists(dummy_filepath)

def test_download_video_missing_params():
    response = client.get("/api/download?url=https://youtube.com/watch&format_id=")
    assert response.status_code == 400
    
    response = client.get("/api/download?url=&format_id=18")
    assert response.status_code == 400
