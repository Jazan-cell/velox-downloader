import os
import glob
import tempfile
from flask import Flask, render_template_string, request, send_file
import yt_dlp

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Velox | Elite Media Engine</title>
    <style>
        :root {
            --bg-deep: #050505;
            --card-bg: rgba(12, 12, 15, 0.75);
            --border-subtle: rgba(212, 175, 55, 0.18);
            --border-glow: rgba(212, 175, 55, 0.6);
            --gold-grad: linear-gradient(135deg, #bf953f 0%, #fcf6ba 25%, #b38728 50%, #fbf5b7 75%, #aa771c 100%);
            --gold-solid: #d4af37;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        
        body {
            background-color: var(--bg-deep);
            background-image: 
                radial-gradient(circle at 50% 0%, rgba(212, 175, 55, 0.08) 0%, transparent 60%),
                linear-gradient(135deg, #050505 0%, #0d0c08 50%, #020202 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
        }

        /* Ambient Dynamic Gold Orbs */
        .glow-orb {
            position: absolute;
            width: 350px;
            height: 350px;
            background: rgba(212, 175, 55, 0.07);
            filter: blur(90px);
            border-radius: 50%;
            z-index: 0;
            pointer-events: none;
            animation: pulseOrb 8s ease-in-out infinite alternate;
        }
        .orb-1 { top: -10%; left: -10%; }
        .orb-2 { bottom: -10%; right: -10%; animation-delay: 4s; }

        @keyframes pulseOrb {
            0% { transform: scale(1); opacity: 0.5; }
            100% { transform: scale(1.2); opacity: 0.9; }
        }

        /* Subtle Luxury Watermark */
        .bg-watermark {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-12deg);
            font-size: 15vw;
            font-weight: 900;
            color: rgba(212, 175, 55, 0.012);
            white-space: nowrap;
            pointer-events: none;
            z-index: 0;
            letter-spacing: 12px;
        }

        .container {
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 440px;
        }

        .card {
            background: var(--card-bg);
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            border: 1px solid var(--border-subtle);
            padding: 32px;
            border-radius: 28px;
            box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.8), 0 0 30px rgba(212, 175, 55, 0.05);
        }

        .brand-header {
            text-align: center;
            margin-bottom: 28px;
        }

        .brand-header h1 {
            font-size: 32px;
            font-weight: 900;
            letter-spacing: -0.5px;
            background: var(--gold-grad);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
            filter: drop-shadow(0 2px 10px rgba(212, 175, 55, 0.2));
        }

        .brand-header p {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 2px;
            opacity: 0.5;
            font-weight: 600;
        }

        .form-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            font-size: 11px;
            font-weight: 700;
            color: var(--gold-solid);
            margin-bottom: 8px;
            letter-spacing: 1px;
            text-transform: uppercase;
            opacity: 0.9;
        }

        /* Gold Glowing Input Box Styling */
        .gold-input-wrapper {
            position: relative;
            border-radius: 14px;
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.4), rgba(20, 20, 25, 0.8));
            padding: 1px; /* Creates the glowing border look */
            transition: all 0.4s ease;
            box-shadow: 0 0 15px rgba(212, 175, 55, 0.15);
        }

        .gold-input-wrapper:focus-within {
            background: var(--gold-grad);
            box-shadow: 0 0 25px rgba(212, 175, 55, 0.4), inset 0 0 10px rgba(212, 175, 55, 0.2);
        }

        input[type="text"], select {
            width: 100%;
            padding: 15px 18px;
            border-radius: 13px;
            border: none;
            background: #09090c;
            color: var(--text-main);
            font-size: 14px;
            outline: none;
            transition: background 0.3s ease;
        }

        input[type="text"]:focus, select:focus {
            background: #0d0d12;
        }

        select {
            border: 1px solid var(--border-subtle);
            cursor: pointer;
        }

        select option {
            background: #0d0d12;
            color: #fff;
        }

        .action-btn {
            background: var(--gold-grad);
            color: #050505;
            border: none;
            padding: 16px;
            font-size: 15px;
            font-weight: 800;
            border-radius: 14px;
            cursor: pointer;
            width: 100%;
            margin-top: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 6px 20px rgba(212, 175, 55, 0.35);
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(212, 175, 55, 0.5);
            filter: brightness(1.1);
        }

        .action-btn:disabled {
            background: #222228;
            color: #555560;
            cursor: not-allowed;
            box-shadow: none;
            transform: none;
        }

        #status {
            margin-top: 18px;
            font-size: 13px;
            text-align: center;
            color: #e5c158;
            min-height: 22px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }

        .footer-credit {
            text-align: center;
            margin-top: 24px;
            font-size: 11px;
            color: var(--text-muted);
            opacity: 0.4;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .hidden { display: none; }
    </style>
</head>
<body>

    <div class="glow-orb orb-1"></div>
    <div class="glow-orb orb-2"></div>
    <div class="bg-watermark">VELOX</div>

    <div class="container">
        <div class="card">
            <div class="brand-header">
                <h1>Velox</h1>
                <p>Download Youtube videos & instagram reels For Free</p>
            </div>
            
            <form id="dlForm" action="/download" method="POST">
                <div class="form-group">
                    <label>Media Link</label>
                    <div class="gold-input-wrapper">
                        <input type="text" name="url" placeholder="Paste YouTube or Reel URL..." required autocomplete="off">
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Extraction Format</label>
                    <select name="mode" id="mode" onchange="toggleMode()">
                        <option value="video">Video (MP4)</option>
                        <option value="audio">Audio Only (MP3)</option>
                    </select>
                </div>

                <div class="form-group" id="video_options">
                    <label>Video Resolution</label>
                    <select name="res">
                        <option value="best">Best Available Quality</option>
                        <option value="1080">1080p Full HD</option>
                        <option value="720">720p HD</option>
                        <option value="360">360p SD</option>
                    </select>
                </div>

                <div class="form-group hidden" id="audio_options">
                    <label>Audio Bitrate Quality</label>
                    <select name="bitrate">
                        <option value="320">320 kbps (Ultra High)</option>
                        <option value="256">256 kbps (High)</option>
                        <option value="192">192 kbps (Medium)</option>
                        <option value="128">128 kbps (Standard)</option>
                    </select>
                </div>

                <button type="submit" id="btn" class="action-btn">Initialize Download</button>
            </form>

            <div id="status"></div>
        </div>
        
        <div class="footer-credit">Engineered by JZN</div>
    </div>

    <script>
        function toggleMode() {
            const mode = document.getElementById('mode').value;
            if (mode === 'video') {
                document.getElementById('video_options').classList.remove('hidden');
                document.getElementById('audio_options').classList.add('hidden');
            } else {
                document.getElementById('video_options').classList.add('hidden');
                document.getElementById('audio_options').classList.remove('hidden');
            }
        }

        document.getElementById('dlForm').onsubmit = function() {
            const btn = document.getElementById('btn');
            btn.disabled = true;
            document.getElementById('status').innerText = "✨ Processing secure media stream... Please wait.";
            setTimeout(() => {
                btn.disabled = false;
                document.getElementById('status').innerText = "⚡ Success! Check your downloads.";
            }, 7000);
        };
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    mode = request.form.get('mode', 'video')
    res = request.form.get('res', 'best')
    bitrate = request.form.get('bitrate', '128')

    if not url:
        return "No URL provided", 400

    temp_dir = tempfile.mkdtemp()
    out_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'outtmpl': out_template,
        'noplaylist': True,
    }

    if mode == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': bitrate,
            }],
        })
    else:
        if res == 'best':
            format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            format_str = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[height<={res}][ext=mp4]/best'

        ydl_opts.update({
            'format': format_str,
            'merge_output_format': 'mp4'
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded_files = glob.glob(os.path.join(temp_dir, '*'))
        if not downloaded_files:
            return "Download extraction failed", 500

        file_path = downloaded_files[0]
        file_name = os.path.basename(file_path)

        return send_file(file_path, as_attachment=True, download_name=file_name)

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
