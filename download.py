#!/usr/bin/env python3
import os
import sys
import argparse
import shutil
import yt_dlp
from downloader import get_ydl_opts, YouTubeDownloader

def download_video(video_url, output_dir=None, format_id='bestvideo+bestaudio/best'):
    print("=" * 60)
    print("           StreamVault CLI - Premium YouTube Downloader")
    print("=" * 60)
    print(f"URL: {video_url}")
    print(f"Format Request: {format_id}")
    if output_dir:
        print(f"Output Directory: {os.path.abspath(output_dir)}")
    print("Initializing download process...")
    
    # Check if ffmpeg is available
    ffmpeg_available = shutil.which('ffmpeg') is not None or shutil.which('ffprobe') is not None
    if not ffmpeg_available:
        print("[WARNING] ffmpeg is not installed on this system.")
        print("          High quality formats (1080p, 4K) may download without audio")
        print("          or fall back to standard quality (usually 720p).")
        print("          Install ffmpeg to enable premium high-definition merging.")
        print("-" * 60)
    
    # 1. Fetch metadata first (without download) to check if the requested format_id is video-only.
    # If the user specified a custom format_id (not the default), and it's video-only, we try to merge if ffmpeg is available.
    try:
        ydl_opts_info = get_ydl_opts({'extract_flat': False})
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
        print(f"Title: {info.get('title')}")
        print(f"Uploader: {info.get('uploader')}")
        print(f"Duration: {info.get('duration_string') or f'{info.get(\'duration\')}s'}")
        print("-" * 60)
        
        # Decide format selection
        if format_id == 'bestvideo+bestaudio/best':
            # Default premium select
            if ffmpeg_available:
                format_sel = 'bestvideo+bestaudio/best'
            else:
                format_sel = 'best'
                print("[INFO] No ffmpeg found. Using combined format ('best') to ensure audio is included.")
        else:
            # Check if user-specified format is video-only
            is_video_only = False
            for f in info.get('formats', []):
                if f.get('format_id') == format_id:
                    vcodec = f.get('vcodec', 'none')
                    acodec = f.get('acodec', 'none')
                    if vcodec != 'none' and acodec == 'none':
                        is_video_only = True
                    break
            
            if is_video_only and ffmpeg_available:
                format_sel = f"{format_id}+bestaudio/best"
                print(f"[INFO] Merging format {format_id} (video only) with best audio stream.")
            else:
                format_sel = format_id
                
    except Exception as e:
        print(f"[WARNING] Could not pre-fetch video metadata: {e}")
        # Fall back to user format_id directly
        format_sel = format_id

    # Create output template
    outtmpl = os.path.join(output_dir or '', '%(title)s.%(ext)s')
    
    ydl_opts_config = {
        'format': format_sel,
        'outtmpl': outtmpl,
        'quiet': False,       # Show download progress in terminal
        'no_warnings': False, # Show warnings in terminal
    }
    
    if ffmpeg_available and ('+' in format_sel or format_sel == 'bestvideo+bestaudio/best'):
        ydl_opts_config['merge_output_format'] = 'mp4'
        
    ydl_opts = get_ydl_opts(ydl_opts_config)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print("=" * 60)
        print("Success! Your video has been downloaded completely.")
        print("=" * 60)
        return True
    except Exception as e:
        print("-" * 60)
        print(f"An error occurred: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YouTube videos in premium quality.")
    parser.add_argument("url", nargs="?", help="The YouTube video URL to download.")
    parser.add_argument("-f", "--format", default="bestvideo+bestaudio/best", 
                        help="yt-dlp format selector (e.g., '137', '22', 'bestaudio'). Default: 'bestvideo+bestaudio/best'")
    parser.add_argument("-o", "--output", default=".", help="Output directory for the downloaded file (default: current directory)")
    
    args = parser.parse_args()
    
    url = args.url
    if not url:
        try:
            url = input("Paste the video URL here: ").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)
        
    if not url:
        print("Error: No URL provided.")
        sys.exit(1)
        
    download_video(url, args.output, args.format)
