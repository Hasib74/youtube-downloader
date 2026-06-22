import os
import uuid
import tempfile
import logging
import yt_dlp

logger = logging.getLogger(__name__)

def format_size(size_bytes):
    if not size_bytes:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def format_duration(seconds):
    if not seconds:
        return "00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def get_cookie_file():
    # 1. Check if a local cookies.txt file exists in the directory
    local_cookies = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.exists(local_cookies):
        return local_cookies
    
    # 2. Check if cookies are passed via environment variables (very useful for Render/Railway)
    env_cookies = os.environ.get("YT_COOKIES")
    if env_cookies:
        logger.info(f"YT_COOKIES env variable found. Length: {len(env_cookies)} chars, Lines: {len(env_cookies.splitlines())}")
        temp_cookies_path = os.path.join(tempfile.gettempdir(), "ytdl_cookies.txt")
        try:
            with open(temp_cookies_path, "w", encoding="utf-8") as f:
                f.write(env_cookies.strip())
            logger.info(f"Saved YT_COOKIES to temporary path: {temp_cookies_path}")
            return temp_cookies_path
        except Exception as e:
            logger.error(f"Error saving YT_COOKIES environment variable to file: {e}")
            
    return None

class YouTubeDownloader:
    @staticmethod
    def get_video_info(url: str) -> dict:
        """
        Extracts metadata and formats for a given YouTube URL.
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Prioritize mobile player clients which have fewer restrictions on server IPs
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            }
        }
        
        cookiefile = get_cookie_file()
        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile
            logger.info(f"Using cookies from: {cookiefile}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                logger.error(f"Failed to fetch video info: {e}")
                raise ValueError(f"Could not retrieve video information. Please check the URL. Details: {str(e)}")

        formats = info.get('formats', [])
        
        # We will categorize formats into three lists:
        # 1. Combined (Video + Audio)
        # 2. Video Only (High resolution, no audio)
        # 3. Audio Only (No video)
        
        combined_formats = []
        video_only_formats = []
        audio_only_formats = []
        
        for f in formats:
            # Skip if format is not HTTP direct download link or does not have format_id
            if not f.get('format_id'):
                continue
                
            f_id = f['format_id']
            ext = f.get('ext', 'mp4')
            filesize = f.get('filesize') or f.get('filesize_approx')
            filesize_str = format_size(filesize)
            
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            
            has_video = vcodec != 'none'
            has_audio = acodec != 'none'
            
            resolution = f.get('resolution')
            if not resolution:
                height = f.get('height')
                width = f.get('width')
                if height:
                    resolution = f"{height}p"
                elif width:
                    resolution = f"{width}px"
                else:
                    resolution = "Unknown"
            
            format_details = {
                'format_id': f_id,
                'url': f.get('url'),
                'ext': ext,
                'resolution': resolution,
                'filesize': filesize,
                'filesize_str': filesize_str,
                'fps': f.get('fps'),
                'tbr': f.get('tbr'), # Total bitrate
                'note': f.get('format_note') or '',
            }
            
            if has_video and has_audio:
                combined_formats.append(format_details)
            elif has_video and not has_audio:
                video_only_formats.append(format_details)
            elif not has_video and has_audio:
                # Add audio specific details
                format_details['abr'] = f.get('abr') # Audio bitrate
                audio_only_formats.append(format_details)
                
        # Sort helper
        def sort_by_resolution_and_bitrate(fmt):
            # Sort by height/resolution if available, else by bitrate
            res_str = fmt['resolution']
            height = 0
            if 'p' in res_str:
                try:
                    height = int(res_str.replace('p', ''))
                except ValueError:
                    pass
            tbr = fmt.get('tbr') or 0
            return (height, tbr)

        combined_formats.sort(key=sort_by_resolution_and_bitrate, reverse=True)
        video_only_formats.sort(key=sort_by_resolution_and_bitrate, reverse=True)
        audio_only_formats.sort(key=lambda x: x.get('abr') or x.get('tbr') or 0, reverse=True)

        return {
            'title': info.get('title'),
            'id': info.get('id'),
            'duration': info.get('duration'),
            'duration_str': format_duration(info.get('duration')),
            'thumbnail': info.get('thumbnail'),
            'uploader': info.get('uploader'),
            'view_count': info.get('view_count'),
            'formats': {
                'combined': combined_formats,
                'video_only': video_only_formats,
                'audio_only': audio_only_formats
            }
        }

    @staticmethod
    def download_format(url: str, format_id: str, download_dir: str = None) -> tuple[str, str]:
        """
        Downloads a specific format for the given YouTube URL.
        If a video-only format is selected, and ffmpeg is installed, yt-dlp will auto-merge it with best audio.
        Returns:
            (filepath, filename)
        """
        if not download_dir:
            download_dir = tempfile.gettempdir()

        unique_id = str(uuid.uuid4())[:8]
        # We prefix the file name with a short unique ID to avoid collision on the server
        outtmpl = os.path.join(download_dir, f"ytdl_{unique_id}_%(title)s.%(ext)s")

        # Set up yt-dlp options
        # If it's a video-only format, try to request format_id + bestaudio so the downloaded file is complete.
        # yt-dlp handles merging using ffmpeg automatically if ffmpeg is on the PATH.
        # We can pass format = f"{format_id}+bestaudio/best" or just format_id if it's combined or audio-only.
        # To make it simple, we check if the requested format_id is video-only by querying metadata,
        # but a cleaner fallback is f"{format_id}+bestaudio/best" for video formats, or just let yt-dlp handle it.
        # Let's specify:
        # format: "format_id+bestaudio/best" if we want to merge, or format_id if it is already combined/audio.
        # Let's try downloading format_id. If the user wants to download exactly what they requested,
        # they might want video-only. However, typically users selecting "video only" on a public website expect it to merge with audio.
        # Let's design it so:
        # If it's a format_id containing only video, we use `format_id+bestaudio/best` (so they get audio too).
        # Otherwise, just `format_id`.
        # To determine if format_id is video-only, we can search the formats. Or we can just pass
        # the format directly. Let's make it flexible:
        # Let's default to downloading exactly the format_id. If we want to offer audio merging, we can handle it in main.py
        # or download it directly.
        # Let's use format_id, but if it fails or if it's video-only, we can let yt-dlp try to merge.
        # Actually, let's just download the exact format_id requested. If they want video+audio, they can choose from the combined list.
        # This keeps the dependencies simple and avoids strict ffmpeg requirement for basic usage!
        ydl_opts = {
            'format': format_id,
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            }
        }

        cookiefile = get_cookie_file()
        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile
            logger.info(f"Using cookies from: {cookiefile}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                logger.error(f"Download failed: {e}")
                raise ValueError(f"Download failed. Details: {str(e)}")
            
            # Find the actual filepath of the downloaded file.
            # Usually prepare_filename works, but if merging happens it might change extension (e.g. mp4 -> mkv).
            filename = ydl.prepare_filename(info)
            actual_filepath = filename

            if not os.path.exists(actual_filepath):
                # 1. Check if the file has been renamed/merged (e.g., info['requested_downloads'])
                req_downloads = info.get('requested_downloads', [])
                if req_downloads and os.path.exists(req_downloads[0].get('filepath', '')):
                    actual_filepath = req_downloads[0]['filepath']
                else:
                    # 2. Scan the temp directory for files matching the unique_id
                    for f in os.listdir(download_dir):
                        if f.startswith(f"ytdl_{unique_id}"):
                            actual_filepath = os.path.join(download_dir, f)
                            break
            
            if not os.path.exists(actual_filepath):
                raise FileNotFoundError(f"Could not locate the downloaded file on the server.")

            return actual_filepath, os.path.basename(actual_filepath)

    @staticmethod
    def get_video_info_simple(url: str) -> dict:
        """
        Extracts simple metadata for a given YouTube URL.
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            }
        }
        cookiefile = get_cookie_file()
        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                logger.error(f"Failed to fetch video info: {e}")
                raise ValueError(f"Could not retrieve video information. Details: {str(e)}")

        # Format upload_date (YYYYMMDD to YYYY-MM-DD)
        upload_date = info.get('upload_date')
        if upload_date and len(upload_date) == 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        else:
            formatted_date = upload_date

        return {
            "title": info.get('title'),
            "author": info.get('uploader') or info.get('channel') or "Unknown",
            "length": info.get('duration'),
            "views": info.get('view_count'),
            "description": info.get('description'),
            "publish_date": formatted_date,
        }

    @staticmethod
    def get_available_resolutions(url: str) -> dict:
        """
        Extracts available progressive and adaptive resolutions for a YouTube URL.
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            }
        }
        cookiefile = get_cookie_file()
        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                logger.error(f"Failed to fetch video info: {e}")
                raise ValueError(f"Could not retrieve video information. Details: {str(e)}")

        formats = info.get('formats', [])
        progressive_resolutions = set()
        all_resolutions = set()

        for f in formats:
            # Check if format has resolution/height
            height = f.get('height')
            if not height:
                continue
            
            res_str = f"{height}p"
            all_resolutions.add(res_str)

            # Progressive means it contains both video and audio
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            if vcodec != 'none' and acodec != 'none':
                progressive_resolutions.add(res_str)

        def sort_resolutions(res_list):
            def get_height(res_str):
                try:
                    return int(res_str.replace('p', ''))
                except ValueError:
                    return 0
            return sorted(list(res_list), key=get_height)

        return {
            "progressive": sort_resolutions(progressive_resolutions),
            "all": sort_resolutions(all_resolutions)
        }

    @staticmethod
    def download_by_resolution(url: str, resolution: str, base_download_dir: str) -> tuple[bool, str]:
        """
        Downloads a video with the specified resolution to a server folder.
        Saves it inside: base_download_dir/{video_id}/
        """
        try:
            # 1. Fetch metadata first to get video_id
            ydl_opts_info = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios', 'web']
                    }
                }
            }
            cookiefile = get_cookie_file()
            if cookiefile:
                ydl_opts_info['cookiefile'] = cookiefile

            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
            
            video_id = info.get('id', 'unknown')
            out_dir = os.path.join(base_download_dir, video_id)
            os.makedirs(out_dir, exist_ok=True)

            # 2. Setup download options
            # If resolution ends with 'p', extract height.
            height = None
            if resolution and resolution.endswith('p'):
                try:
                    height = int(resolution[:-1])
                except ValueError:
                    pass

            # Setup format selection
            if height:
                # Select bestvideo with specified height + bestaudio, merging them into mp4.
                # Fallback to general best if height is not found.
                format_sel = f"bestvideo[height={height}]+bestaudio/best[height={height}]/best"
            elif resolution == 'audio':
                format_sel = "bestaudio/best"
            else:
                format_sel = "bestvideo+bestaudio/best"

            outtmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
            
            ydl_opts = {
                'format': format_sel,
                'outtmpl': outtmpl,
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4',  # Ensure output is mp4 if merging
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios', 'web']
                    }
                }
            }
            
            if cookiefile:
                ydl_opts['cookiefile'] = cookiefile

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            return True, None
        except Exception as e:
            logger.error(f"Download by resolution failed: {e}")
            return False, str(e)
