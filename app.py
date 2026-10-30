import os
import uuid
import time
import shutil
import threading
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

# Temporary download directory
TEMP_DIR = os.path.join(os.getcwd(), 'temp_downloads')
os.makedirs(TEMP_DIR, exist_ok=True)

# Active download progress store for real-time tracking
download_progress = {}

def cleanup_old_files():
    """Background cleanup for temporary files older than 30 minutes."""
    while True:
        try:
            now = time.time()
            if os.path.exists(TEMP_DIR):
                for f in os.listdir(TEMP_DIR):
                    file_path = os.path.join(TEMP_DIR, f)
                    if os.path.isfile(file_path) and (now - os.path.getmtime(file_path)) > 1800:
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(600)

threading.Thread(target=cleanup_old_files, daemon=True).start()

def get_base_ydl_opts():
    """Base yt-dlp options incorporating cookies.txt if present."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 15,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
    return opts

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/scan', methods=['POST'])
def scan_media():
    data = request.get_json() or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please enter a valid media URL.'}), 400

    if not any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'instagram.com']):
        return jsonify({'error': 'Only YouTube and Instagram URLs are supported.'}), 400

    ydl_opts = get_base_ydl_opts()
    ydl_opts['extract_flat'] = False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({'error': 'Could not extract media information.'}), 400

            title = info.get('title', 'Unknown Title')
            duration = info.get('duration', 0)
            thumbnail = info.get('thumbnail', '')
            uploader = info.get('uploader', info.get('channel', 'Unknown Creator'))
            platform = 'Instagram' if 'instagram.com' in url.lower() else 'YouTube'

            formats = info.get('formats', [])
            video_options = []
            audio_options = []
            seen_res = set()

            for f in formats:
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                height = f.get('height')
                ext = f.get('ext')
                format_id = f.get('format_id')

                # Video streams (muxed or video-only)
                if height and height >= 144 and vcodec != 'none':
                    res_label = f"{height}p"
                    if height >= 2160:
                        res_label = "4K Ultra HD"
                    elif height >= 1440:
                        res_label = "1440p QHD"
                    elif height >= 1080:
                        res_label = "1080p Full HD"
                    elif height >= 720:
                        res_label = "720p HD"
                    elif height >= 480:
                        res_label = "480p"
                    elif height >= 360:
                        res_label = "360p"

                    if height not in seen_res:
                        seen_res.add(height)
                        video_options.append({
                            'format_id': format_id,
                            'resolution': res_label,
                            'height': height,
                            'ext': ext or 'mp4'
                        })

            # Sort video resolutions descending
            video_options = sorted(video_options if isinstance(video_options, list) else [], key=lambda x: x['height'], reverse=True)
            formatted_videos = []
            for v in video_options:
                formatted_videos.append({
                    'format_id': v['format_id'],
                    'quality': v['resolution'],
                    'ext': 'mp4'
                })

            # Standard audio presets
            audio_options = [
                {'bitrate': '320 kbps', 'format_id': 'bestaudio'},
                {'bitrate': '256 kbps', 'format_id': 'bestaudio'},
                {'bitrate': '192 kbps', 'format_id': 'bestaudio'},
                {'bitrate': '128 kbps', 'format_id': 'bestaudio'}
            ]

            job_id = str(uuid.uuid4())

            return jsonify({
                'success': True,
                'job_id': job_id,
                'title': title,
                'duration': duration,
                'thumbnail': thumbnail,
                'uploader': uploader,
                'platform': platform,
                'videos': formatted_videos if formatted_videos else [{'format_id': 'best', 'quality': 'Best Available', 'ext': 'mp4'}],
                'audios': audio_options,
                'original_url': url
            })

    except Exception as e:
        err_msg = str(e)
        if 'Sign in' in err_msg or 'private' in err_msg.lower():
            err_msg = 'Content is private, restricted, or requires authentication.'
        return jsonify({'error': f'Extraction failed: {err_msg}'}), 400

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.get_json() or {}
    url = data.get('url')
    format_id = data.get('format_id')
    file_type = data.get('type', 'video')
    job_id = str(uuid.uuid4())

    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    def run_download():
        try:
            download_progress[job_id] = {'status': 'downloading', 'progress': 0, 'filename': None}
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    p_str = d.get('_percent_str', '0%').replace('%', '').strip()
                    try:
                        p_val = float(p_str)
                    except ValueError:
                        p_val = 0.0
                    download_progress[job_id]['progress'] = p_val

            ydl_opts = get_base_ydl_opts()
            ydl_opts['progress_hooks'] = [progress_hook]
            ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'{job_id}_%(title)s.%(ext)s')

            if file_type == 'audio':
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                if format_id == 'best':
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                else:
                    ydl_opts['format'] = f'{format_id}+bestaudio/best'
                ydl_opts['merge_output_format'] = 'mp4'

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if file_type == 'audio':
                    filename = os.path.splitext(filename)[0] + '.mp3'
                else:
                    filename = os.path.splitext(filename)[0] + '.mp4'

                if not os.path.exists(filename):
                    for f in os.listdir(TEMP_DIR):
                        if f.startswith(job_id):
                            filename = os.path.join(TEMP_DIR, f)
                            break

                download_progress[job_id] = {'status': 'completed', 'progress': 100, 'filename': filename}

        except Exception as e:
            download_progress[job_id] = {'status': 'error', 'message': str(e)}

    threading.Thread(target=run_download, daemon=True).start()
    return jsonify({'success': True, 'job_id': job_id})

@app.route('/api/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    prog = download_progress.get(job_id)
    if not prog:
        return jsonify({'status': 'not_found'}), 404
    return jsonify(prog)

@app.route('/api/file/<job_id>', methods=['GET'])
def get_file(job_id):
    prog = download_progress.get(job_id)
    if not prog or prog.get('status') != 'completed':
        return "File not ready or expired", 404

    filepath = prog.get('filename')
    if not filepath or not os.path.exists(filepath):
        return "File not found on server", 404

    return send_file(filepath, as_attachment=True)

# ==================== HTML / CSS / JS FRONTEND ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VELOX — Ultimate Media Downloader</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-obsidian: #030304;
            --surface-dark: #0a0a0d;
            --surface-card: #111116;
            --gold-primary: #ffd700;
            --gold-bright: #fff099;
            --accent-orange: #ff6b00;
            --text-main: #ffffff;
            --text-muted: #8e9bb0;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg-obsidian);
            color: var(--text-main);
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }

        /* 1.5s CINEMATIC LIQUID GLOW INTRO OVERLAY */
        #intro-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: #020202;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            animation: introFadeOut 0.4s ease 1.5s forwards;
            pointer-events: none;
        }

        .intro-logo-box {
            position: relative;
            text-align: center;
        }

        .intro-title {
            font-size: 52px;
            font-weight: 900;
            letter-spacing: 8px;
            text-transform: uppercase;
            background: linear-gradient(135deg, #ffffff 10%, var(--gold-primary) 50%, var(--accent-orange) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 25px rgba(255, 215, 0, 0.8));
            animation: introPulse 1.2s ease-in-out infinite alternate;
        }

        .intro-subtitle {
            font-size: 13px;
            letter-spacing: 4px;
            text-transform: uppercase;
            font-weight: 700;
            color: var(--gold-bright);
            margin-top: 10px;
            text-shadow: 0 0 15px rgba(255, 215, 0, 0.9), 0 0 30px rgba(255, 107, 0, 0.6);
        }

        @keyframes introPulse {
            0% { transform: scale(0.96); filter: drop-shadow(0 0 15px rgba(255, 215, 0, 0.5)); }
            100% { transform: scale(1.04); filter: drop-shadow(0 0 35px rgba(255, 215, 0, 1)); }
        }

        @keyframes introFadeOut {
            0% { opacity: 1; visibility: visible; }
            100% { opacity: 0; visibility: hidden; }
        }

        /* Cinematic Atmosphere Background */
        .ambient-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: -1;
            background: radial-gradient(circle at 50% 15%, rgba(255, 107, 0, 0.12) 0%, rgba(3, 3, 4, 1) 75%),
                        radial-gradient(circle at 85% 85%, rgba(255, 215, 0, 0.08) 0%, transparent 60%);
            pointer-events: none;
        }

        .particles {
            position: absolute;
            width: 100%;
            height: 100%;
            background-image: radial-gradient(rgba(255, 215, 0, 0.18) 1px, transparent 1px);
            background-size: 45px 45px;
            opacity: 0.35;
            animation: drift 35s linear infinite;
        }

        @keyframes drift {
            0% { background-position: 0 0; }
            100% { background-position: 90px 90px; }
        }

        /* Header */
        header {
            text-align: center;
            padding: 45px 20px 20px;
        }

        .brand-logo {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }

        .brand-logo i {
            font-size: 32px;
            color: var(--gold-primary);
            filter: drop-shadow(0 0 15px rgba(255, 215, 0, 0.8));
        }

        h1 {
            font-size: 36px;
            font-weight: 900;
            letter-spacing: 4px;
            background: linear-gradient(135deg, #fff 20%, var(--gold-primary) 60%, var(--accent-orange) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-transform: uppercase;
        }

        .tagline {
            color: var(--text-muted);
            font-size: 13px;
            letter-spacing: 2px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .container {
            max-width: 700px;
            margin: 20px auto 60px;
            padding: 0 20px;
        }

        /* MASTERPIECE LIQUID NEON BORDER CONTAINER */
        .liquid-neon-box {
            position: relative;
            border-radius: 26px;
            padding: 3px;
            background: linear-gradient(120deg, #ffd700, #ff6b00, #fff099, #111116, #ff8c00, #ffd700);
            background-size: 400% 400%;
            animation: liquidFlow 7s ease infinite;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.35), 0 0 50px rgba(255, 107, 0, 0.25), inset 0 0 15px rgba(255, 215, 0, 0.2);
            margin-bottom: 30px;
        }

        .liquid-neon-box::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: inherit;
            border-radius: 28px;
            filter: blur(12px);
            opacity: 0.7;
            z-index: -1;
            animation: liquidFlow 7s ease infinite;
        }

        @keyframes liquidFlow {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .card-inner {
            background: var(--surface-card);
            border-radius: 23px;
            padding: 35px 30px;
            backdrop-filter: blur(16px);
        }

        /* URL Input Section */
        .input-group {
            position: relative;
            margin-bottom: 25px;
        }

        .url-input-wrapper {
            position: relative;
            display: flex;
            align-items: center;
        }

        .url-input-wrapper i.prefix-icon {
            position: absolute;
            left: 18px;
            color: var(--gold-primary);
            font-size: 18px;
        }

        input[type="text"] {
            width: 100%;
            background: var(--surface-dark);
            border: 2px solid rgba(255, 215, 0, 0.25);
            border-radius: 14px;
            padding: 16px 50px 16px 50px;
            color: var(--text-main);
            font-size: 16px;
            outline: none;
            transition: all 0.3s ease;
        }

        input[type="text"]:focus {
            border-color: var(--gold-primary);
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.4), inset 0 0 10px rgba(255, 215, 0, 0.1);
        }

        .input-actions {
            position: absolute;
            right: 12px;
            display: flex;
            gap: 8px;
        }

        .icon-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 16px;
            padding: 6px;
            border-radius: 8px;
            transition: color 0.2s;
        }

        .icon-btn:hover {
            color: var(--gold-primary);
        }

        /* Main Download Button */
        .btn-primary {
            width: 100%;
            background: linear-gradient(135deg, var(--gold-primary), var(--accent-orange));
            color: #000;
            border: none;
            padding: 18px;
            border-radius: 14px;
            font-size: 16px;
            font-weight: 800;
            letter-spacing: 1.5px;
            cursor: pointer;
            text-transform: uppercase;
            box-shadow: 0 8px 25px rgba(255, 107, 0, 0.4), 0 0 15px rgba(255, 215, 0, 0.3);
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
            overflow: hidden;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 35px rgba(255, 215, 0, 0.7), 0 0 20px rgba(255, 107, 0, 0.5);
        }

        .btn-primary:active {
            transform: translateY(1px);
        }

        /* Panels */
        .panel {
            display: none;
            animation: fadeIn 0.4s ease forwards;
        }

        .panel.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Scanning State */
        .scanning-box {
            text-align: center;
            padding: 40px 0;
        }

        .spinner {
            width: 60px;
            height: 60px;
            border: 4px solid rgba(255, 215, 0, 0.15);
            border-top: 4px solid var(--gold-primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .scan-status {
            color: var(--gold-bright);
            font-weight: 600;
            font-size: 15px;
            letter-spacing: 0.5px;
        }

        /* Results & Media Info */
        .media-info {
            display: flex;
            gap: 15px;
            background: var(--surface-dark);
            padding: 15px;
            border-radius: 14px;
            margin-bottom: 25px;
            align-items: center;
            border: 1px solid rgba(255, 215, 0, 0.2);
            box-shadow: inset 0 0 10px rgba(255, 215, 0, 0.05);
        }

        .media-thumbnail {
            width: 100px;
            height: 65px;
            object-fit: cover;
            border-radius: 8px;
            background: #000;
        }

        .media-details h3 {
            font-size: 15px;
            font-weight: 600;
            margin-bottom: 6px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .media-meta {
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            gap: 12px;
        }

        /* Quality Options Grid */
        .section-title {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--gold-primary);
            margin: 20px 0 10px;
            font-weight: 800;
        }

        .quality-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 20px;
        }

        .quality-card {
            background: var(--surface-dark);
            border: 2px solid rgba(255, 215, 0, 0.18);
            padding: 12px 15px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.25s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .quality-card:hover {
            border-color: var(--gold-primary);
            background: rgba(255, 215, 0, 0.08);
            box-shadow: 0 0 12px rgba(255, 215, 0, 0.25);
        }

        .quality-card.selected {
            border-color: var(--gold-primary);
            background: rgba(255, 215, 0, 0.15);
            box-shadow: 0 0 18px rgba(255, 215, 0, 0.4);
        }

        .quality-card .q-name {
            font-weight: 700;
            font-size: 14px;
        }

        .quality-card .q-type {
            font-size: 11px;
            color: var(--text-muted);
        }

        /* Progress State */
        .progress-container {
            text-align: center;
            padding: 20px 0;
        }

        .progress-bar-bg {
            width: 100%;
            height: 10px;
            background: var(--surface-dark);
            border-radius: 5px;
            overflow: hidden;
            margin: 20px 0;
            border: 1px solid rgba(255, 215, 0, 0.25);
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-orange), var(--gold-primary));
            width: 0%;
            transition: width 0.3s ease;
            box-shadow: 0 0 12px var(--gold-primary);
        }

        /* Error Box */
        .error-box {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.4);
            padding: 20px;
            border-radius: 14px;
            text-align: center;
            color: #f87171;
            margin-bottom: 20px;
        }

        /* Toast Notifications */
        #toast-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
        }

        .toast {
            background: var(--surface-card);
            border: 1px solid var(--gold-primary);
            color: #fff;
            padding: 12px 20px;
            border-radius: 10px;
            margin-top: 10px;
            box-shadow: 0 5px 25px rgba(0,0,0,0.7), 0 0 10px rgba(255, 215, 0, 0.3);
            font-size: 14px;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* LIVELY GLOW FOOTER BRANDING */
        footer {
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            padding: 25px;
            letter-spacing: 2px;
            text-transform: uppercase;
            font-weight: 700;
        }

        .footer-branding {
            background: linear-gradient(135deg, var(--gold-bright), var(--accent-orange));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 12px rgba(255, 215, 0, 0.6);
            animation: glowPulse 2s ease-in-out infinite alternate;
        }

        @keyframes glowPulse {
            0% { filter: drop-shadow(0 0 4px rgba(255, 215, 0, 0.4)); }
            100% { filter: drop-shadow(0 0 12px rgba(255, 215, 0, 0.9)); }
        }

        @media(max-width: 480px) {
            .quality-grid {
                grid-template-columns: 1fr;
            }
            h1 { font-size: 28px; }
            .intro-title { font-size: 38px; }
        }
    </style>
</head>
<body>

    <!-- 1.5-SECOND CINEMATIC INTRO OVERLAY -->
    <div id="intro-overlay">
        <div class="intro-logo-box">
            <div class="intro-title">VELOX</div>
            <div class="intro-subtitle">ENGINEERED BY JAZAN</div>
        </div>
    </div>

    <div class="ambient-bg">
        <div class="particles"></div>
    </div>

    <header>
        <div class="brand-logo">
            <i class="fa-solid fa-bolt-lightning"></i>
            <h1>VELOX</h1>
        </div>
        <p class="tagline">Ultimate Multi-Quality Media Engine</p>
    </header>

    <div class="container">
        <!-- LIQUID NEON GLOW CONTAINER -->
        <div class="liquid-neon-box">
            <div class="card-inner">
                
                <!-- IDLE / URL INPUT PANEL -->
                <div id="panel-input" class="panel active">
                    <div class="input-group">
                        <div class="url-input-wrapper">
                            <i class="fa-solid fa-link prefix-icon"></i>
                            <input type="text" id="url-input" placeholder="Paste YouTube or Instagram link here..." autocomplete="off">
                            <div class="input-actions">
                                <button class="icon-btn" id="paste-btn" title="Paste from clipboard"><i class="fa-solid fa-clipboard"></i></button>
                                <button class="icon-btn" id="clear-btn" title="Clear URL"><i class="fa-solid fa-xmark"></i></button>
                            </div>
                        </div>
                    </div>
                    <button class="btn-primary" id="scan-btn">Download Media</button>
                </div>

                <!-- SCANNING PANEL -->
                <div id="panel-scanning" class="panel">
                    <div class="scanning-box">
                        <div class="spinner"></div>
                        <div class="scan-status" id="scan-status-text">Analyzing media stream...</div>
                    </div>
                </div>

                <!-- RESULTS / QUALITY SELECT PANEL -->
                <div id="panel-results" class="panel">
                    <div class="media-info">
                        <img id="res-thumb" src="" alt="Thumbnail" class="media-thumbnail">
                        <div class="media-details">
                            <h3 id="res-title">Media Title</h3>
                            <div class="media-meta">
                                <span id="res-platform"><i class="fa-solid fa-globe"></i> YouTube</span>
                                <span id="res-duration"><i class="fa-regular fa-clock"></i> 0:00</span>
                            </div>
                        </div>
                    </div>

                    <div class="section-title">Video Quality Options</div>
                    <div class="quality-grid" id="video-options-grid">
                        <!-- Injected via JS -->
                    </div>

                    <div class="section-title">Audio Quality Options</div>
                    <div class="quality-grid" id="audio-options-grid">
                        <!-- Injected via JS -->
                    </div>

                    <button class="btn-primary" id="download-trigger-btn" style="margin-top: 10px;">Start Download</button>
                </div>

                <!-- DOWNLOADING PANEL -->
                <div id="panel-downloading" class="panel">
                    <div class="progress-container">
                        <div class="spinner" style="width: 45px; height: 45px; border-width: 3px;"></div>
                        <h3 style="margin-bottom: 10px; font-size: 18px;">Processing & Downloading...</h3>
                        <p id="download-status-text" style="color: var(--text-muted); font-size: 13px;">Preparing streams and merging formats</p>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" id="progress-fill"></div>
                        </div>
                        <span id="progress-percentage" style="font-weight: 700; color: var(--gold-primary);">0%</span>
                    </div>
                </div>

                <!-- ERROR PANEL -->
                <div id="panel-error" class="panel">
                    <div class="error-box">
                        <i class="fa-solid fa-triangle-exclamation" style="font-size: 28px; margin-bottom: 10px;"></i>
                        <h3 style="margin-bottom: 5px;">Extraction Failed</h3>
                        <p id="error-message-text" style="font-size: 13px; color: #fca5a5;">An unexpected error occurred while parsing media.</p>
                    </div>
                    <button class="btn-primary" id="retry-btn">Try Another Link</button>
                </div>

            </div>
        </div>
    </div>

    <footer>
        <span class="footer-branding">Engineered by Jazan</span> &bull; Velox v3.0
    </footer>

    <div id="toast-container"></div>

    <script>
        let currentJobData = null;
        let selectedFormat = { id: null, type: 'video' };

        function showPanel(panelId) {
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.getElementById(panelId).classList.add('active');
        }

        function showToast(message) {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.innerText = message;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // URL Actions
        document.getElementById('clear-btn').addEventListener('click', () => {
            document.getElementById('url-input').value = '';
        });

        document.getElementById('paste-btn').addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                document.getElementById('url-input').value = text;
                showToast('URL pasted from clipboard');
            } catch (err) {
                showToast('Clipboard access denied');
            }
        });

        // Scan Action
        document.getElementById('scan-btn').addEventListener('click', async () => {
            const url = document.getElementById('url-input').value.trim();
            if (!url) {
                showToast('Please paste a valid URL');
                return;
            }

            showPanel('panel-scanning');
            
            const statuses = ["Connecting to media stream...", "Analyzing available formats...", "Detecting resolutions...", "Finalizing options..."];
            let sIdx = 0;
            const statusInterval = setInterval(() => {
                sIdx = (sIdx + 1) % statuses.length;
                document.getElementById('scan-status-text').innerText = statuses[sIdx];
            }, 1000);

            try {
                const response = await fetch('/api/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });

                const data = await response.json();
                clearInterval(statusInterval);

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to scan URL');
                }

                currentJobData = data;
                renderResults(data);
                showPanel('panel-results');

            } catch (err) {
                clearInterval(statusInterval);
                document.getElementById('error-message-text').innerText = err.message;
                showPanel('panel-error');
            }
        });

        function renderResults(data) {
            document.getElementById('res-title').innerText = data.title;
            document.getElementById('res-thumb').src = data.thumbnail || 'https://via.placeholder.com/100x65?text=VELOX';
            document.getElementById('res-platform').innerHTML = `<i class="fa-solid fa-globe"></i> ${data.platform}`;
            
            const mins = Math.floor(data.duration / 60);
            const secs = data.duration % 60;
            document.getElementById('res-duration').innerHTML = `<i class="fa-regular fa-clock"></i> ${mins}:${secs < 10 ? '0' : ''}${secs}`;

            // Render Video Options
            const vGrid = document.getElementById('video-options-grid');
            vGrid.innerHTML = '';
            if (data.videos && data.videos.length > 0) {
                data.videos.forEach((v, idx) => {
                    const card = document.createElement('div');
                    card.className = `quality-card ${idx === 0 ? 'selected' : ''}`;
                    card.innerHTML = `<div><div class="q-name">${v.quality}</div><div class="q-type">MP4 Video</div></div><i class="fa-solid fa-circle-check" style="color: ${idx === 0 ? 'var(--gold-primary)' : 'transparent'};"></i>`;
                    
                    if (idx === 0) {
                        selectedFormat = { id: v.format_id, type: 'video' };
                    }

                    card.addEventListener('click', () => {
                        document.querySelectorAll('.quality-grid .quality-card').forEach(c => {
                            c.classList.remove('selected');
                            c.querySelector('i').style.color = 'transparent';
                        });
                        card.classList.add('selected');
                        card.querySelector('i').style.color = 'var(--gold-primary)';
                        selectedFormat = { id: v.format_id, type: 'video' };
                    });
                    vGrid.appendChild(card);
                });
            }

            // Render Audio Options
            const aGrid = document.getElementById('audio-options-grid');
            aGrid.innerHTML = '';
            if (data.audios && data.audios.length > 0) {
                data.audios.forEach((a, idx) => {
                    const card = document.createElement('div');
                    card.className = 'quality-card';
                    card.innerHTML = `<div><div class="q-name">${a.bitrate}</div><div class="q-type">MP3 Audio</div></div><i class="fa-solid fa-circle-check" style="color: transparent;"></i>`;
                    
                    card.addEventListener('click', () => {
                        document.querySelectorAll('.quality-grid .quality-card').forEach(c => {
                            c.classList.remove('selected');
                            c.querySelector('i').style.color = 'transparent';
                        });
                        card.classList.add('selected');
                        card.querySelector('i').style.color = 'var(--gold-primary)';
                        selectedFormat = { id: a.format_id, type: 'audio' };
                    });
                    aGrid.appendChild(card);
                });
            }
        }

        // Trigger Download Execution
        document.getElementById('download-trigger-btn').addEventListener('click', async () => {
            if (!currentJobData || !selectedFormat.id) {
                showToast('Please select a valid quality');
                return;
            }

            showPanel('panel-downloading');

            try {
                const response = await fetch('/api/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: currentJobData.original_url,
                        format_id: selectedFormat.id,
                        type: selectedFormat.type
                    })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Download failed to start');

                const jobId = data.job_id;
                const pollInterval = setInterval(async () => {
                    const pRes = await fetch(`/api/progress/${jobId}`);
                    const pData = await pRes.json();

                    if (pData.status === 'downloading') {
                        const prog = Math.round(pData.progress || 0);
                        document.getElementById('progress-fill').style.width = prog + '%';
                        document.getElementById('progress-percentage').innerText = prog + '%';
                    } else if (pData.status === 'completed') {
                        clearInterval(pollInterval);
                        document.getElementById('progress-fill').style.width = '100%';
                        document.getElementById('progress-percentage').innerText = '100%';
                        showToast('Download complete! Starting file download...');
                        
                        window.location.href = `/api/file/${jobId}`;
                        
                        setTimeout(() => {
                            showPanel('panel-input');
                            document.getElementById('url-input').value = '';
                        }, 2500);
                    } else if (pData.status === 'error') {
                        clearInterval(pollInterval);
                        document.getElementById('error-message-text').innerText = pData.message || 'Download error';
                        showPanel('panel-error');
                    }
                }, 1000);

            } catch (err) {
                document.getElementById('error-message-text').innerText = err.message;
                showPanel('panel-error');
            }
        });

        document.getElementById('retry-btn').addEventListener('click', () => {
            showPanel('panel-input');
            document.getElementById('url-input').value = '';
        });
    </script>
    <div style="text-align: center; margin: 30px 0; padding-bottom: 20px;">
    <a href="instagram://user?username=jjjjz777777" onclick="setTimeout(function(){window.location = 'https://instagram.com/jjjjz777777';}, 25);" target="_blank" style="color: #ffd700; text-decoration: none; font-family: monospace; font-size: 14px; display: inline-flex; align-items: center; gap: 10px; background: rgba(255, 215, 0, 0.05); padding: 10px 20px; border-radius: 20px; border: 1px solid rgba(255, 215, 0, 0.2);">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 16 16"><path d="M8 0C5.829 0 5.556.01 4.703.048 3.85.088 3.269.222 2.76.42a3.917 3.917 0 0 0-1.417.923A3.927 3.927 0 0 0 .42 2.76C.222 3.268.087 3.85.048 4.7.01 5.555 0 5.827 0 8.001c0 2.172.01 2.444.048 3.297.04.852.174 1.433.372 1.942.205.526.478.972.923 1.417.444.445.89.719 1.416.923.51.198 1.09.333 1.942.372C5.555 15.99 5.827 16 8 16s2.444-.01 3.298-.048c.851-.04 1.434-.174 1.943-.372a3.916 3.916 0 0 0 1.416-.923c.445-.445.718-.891.923-1.417.197-.509.332-1.09.372-1.942C15.99 10.445 16 10.173 16 8s-.01-2.445-.048-3.299c-.04-.851-.175-1.433-.372-1.941a3.926 3.926 0 0 0-.923-1.417A3.911 3.911 0 0 0 13.24.42c-.51-.198-1.092-.333-1.943-.372C10.443.01 10.172 0 7.998 0h.003zm-.717 1.442h.718c2.136 0 2.389.007 3.232.046.78.035 1.204.166 1.486.275.373.145.64.319.92.599.28.28.453.546.598.92.11.281.24.705.275 1.485.039.843.047 1.096.047 3.231s-.008 2.389-.047 3.232c-.035.78-.166 1.203-.275 1.485a2.47 2.47 0 0 1-.599.919c-.28.28-.546.453-.92.598-.282.11-.705.24-1.485.276-.843.038-1.096.047-3.232.047s-2.39-.009-3.233-.047c-.78-.036-1.203-.166-1.485-.276a2.478 2.478 0 0 1-.92-.598 2.48 0 0 1-.6-.92c-.109-.281-.24-.705-.275-1.485-.038-.843-.046-1.096-.046-3.233 0-2.136.008-2.388.046-3.231.036-.78.166-1.204.276-1.486.145-.373.319-.64.599-.92.28-.28.546-.453.92-.598.282-.11.705-.24 1.485-.276.738-.034 1.024-.044 2.515-.045v.002zm4.988 1.328a.96.96 0 1 0 0 1.92.96.96 0 0 0 0-1.92zm-4.27 1.122a4.109 4.109 0 1 0 0 8.217 4.109 4.109 0 0 0 0-8.217zm0 1.441a2.668 2.668 0 1 1 0 5.335 2.668 2.668 0 0 1 0-5.335z"/></svg>
        <span>jjjjz777777</span>
    </a>
</div>

</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
