import os
import re
from flask import Flask, render_template_string, request, jsonify
import yt_dlp

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VELOX — Cinematic Media Downloader</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-obsidian: #050608;
            --card-glass: rgba(12, 14, 20, 0.85);
            --gold-accent: #f1c40f;
            --gold-bright: #ffea79;
            --gold-gradient: linear-gradient(135deg, #f39c12, #f1c40f, #ffe600);
            --text-main: #f4f5f7;
            --text-muted: #8e92a4;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        body {
            background-color: var(--bg-obsidian);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow: hidden;
            background-image: 
                radial-gradient(circle at 50% -20%, rgba(241, 196, 15, 0.15), transparent 60%),
                radial-gradient(circle at 50% 120%, rgba(243, 156, 18, 0.08), transparent 50%);
        }

        /* Cinematic Intro Overlay */
        #intro-screen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: #030406;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            animation: fadeOutIntro 0.5s ease-in-out 1.5s forwards;
        }

        @keyframes fadeOutIntro {
            0% { opacity: 1; visibility: visible; }
            100% { opacity: 0; visibility: hidden; }
        }

        .intro-logo {
            font-size: 3.5rem;
            font-weight: 700;
            background: var(--gold-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 5px;
            text-transform: uppercase;
            animation: introZoom 1.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .intro-sub {
            color: var(--gold-accent);
            font-size: 0.9rem;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-top: 10px;
            opacity: 0.8;
            animation: introZoom 1.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes introZoom {
            0% { transform: scale(0.9); opacity: 0; filter: blur(10px); }
            50% { transform: scale(1); opacity: 1; filter: blur(0); }
            100% { transform: scale(1.05); opacity: 1; filter: blur(0); }
        }

        /* After Effects Saber Neon Glow Effect */
        @keyframes saberGlow {
            0% {
                border-color: rgba(241, 196, 15, 0.6);
                box-shadow: 0 0 10px rgba(241, 196, 15, 0.3), 
                            0 0 25px rgba(243, 156, 18, 0.3), 
                            inset 0 0 12px rgba(241, 196, 15, 0.2);
            }
            50% {
                border-color: rgba(255, 234, 121, 1);
                box-shadow: 0 0 20px rgba(241, 196, 15, 0.7), 
                            0 0 45px rgba(243, 156, 18, 0.8), 
                            0 0 70px rgba(241, 196, 15, 0.5), 
                            inset 0 0 22px rgba(255, 234, 121, 0.5);
            }
            100% {
                border-color: rgba(241, 196, 15, 0.6);
                box-shadow: 0 0 10px rgba(241, 196, 15, 0.3), 
                            0 0 25px rgba(243, 156, 18, 0.3), 
                            inset 0 0 12px rgba(241, 196, 15, 0.2);
            }
        }

        .container {
            width: 100%;
            max-width: 620px;
            background: var(--card-glass);
            backdrop-filter: blur(30px);
            -webkit-backdrop-filter: blur(30px);
            border: 2px solid rgba(241, 196, 15, 0.5);
            border-radius: 30px;
            padding: 40px 30px;
            animation: saberGlow 3s infinite ease-in-out, containerEntrance 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            animation-delay: 1.5s;
            opacity: 0;
        }

        @keyframes containerEntrance {
            from { opacity: 0; transform: translateY(30px) scale(0.97); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo-title {
            font-size: 2.6rem;
            font-weight: 700;
            background: var(--gold-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 3px;
            margin-bottom: 4px;
            text-transform: uppercase;
        }

        .subtitle {
            color: var(--text-muted);
            font-size: 0.9rem;
            letter-spacing: 0.5px;
        }

        .input-group {
            position: relative;
            margin-bottom: 20px;
        }

        .url-input {
            width: 100%;
            padding: 18px 20px;
            background: rgba(5, 6, 8, 0.9);
            border: 1.5px solid rgba(241, 196, 15, 0.3);
            border-radius: 16px;
            color: #fff;
            font-size: 1rem;
            outline: none;
        }

        .url-input:focus {
            border-color: var(--gold-bright);
            box-shadow: 0 0 15px rgba(241, 196, 15, 0.4);
        }

        .btn-submit {
            width: 100%;
            padding: 16px;
            background: var(--gold-gradient);
            border: none;
            border-radius: 16px;
            color: #050608;
            font-weight: 700;
            font-size: 1.05rem;
            cursor: pointer;
            box-shadow: 0 8px 25px rgba(241, 196, 15, 0.3);
        }

        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 35px rgba(241, 196, 15, 0.5);
        }

        /* Result & Quality Selector Area */
        #result-area {
            margin-top: 25px;
            display: none;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 5px;
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: rgba(241, 196, 15, 0.3); border-radius: 10px; }

        .media-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(241, 196, 15, 0.25);
            border-radius: 18px;
            padding: 20px;
        }

        .media-title {
            font-size: 1rem;
            margin-bottom: 15px;
            color: #fff;
            font-weight: 600;
            line-height: 1.4;
        }

        .quality-section-title {
            font-size: 0.85rem;
            color: var(--gold-accent);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 15px 0 8px 0;
            font-weight: 700;
        }

        .quality-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .quality-btn {
            padding: 12px 15px;
            background: rgba(241, 196, 15, 0.08);
            border: 1px solid rgba(241, 196, 15, 0.3);
            color: var(--text-main);
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            text-align: center;
            display: block;
        }

        .quality-btn:hover {
            background: var(--gold-gradient);
            color: #050608;
            border-color: transparent;
            box-shadow: 0 5px 20px rgba(241, 196, 15, 0.4);
        }

        .spinner {
            display: none;
            width: 32px;
            height: 32px;
            border: 3px solid rgba(241, 196, 15, 0.2);
            border-top: 3px solid var(--gold-accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 20px auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>

    <!-- Cinematic Intro Screen -->
    <div id="intro-screen">
        <h1 class="intro-logo">VELOX</h1>
        <p class="intro-sub">Engineered by Jazan</p>
    </div>

    <div class="container">
        <div class="header">
            <h1 class="logo-title">VELOX</h1>
            <p class="subtitle">Ultimate Multi-Quality Media Downloader</p>
        </div>

        <div class="input-group">
            <input type="text" id="urlInput" class="url-input" placeholder="Paste YouTube or Instagram link..." autocomplete="off">
        </div>

        <button id="fetchBtn" class="btn-submit" onclick="fetchMediaFormats()">Scan Qualities</button>

        <div id="spinner" class="spinner"></div>

        <div id="result-area"></div>
    </div>

    <script>
        async function fetchMediaFormats() {
            const urlInput = document.getElementById('urlInput').value.trim();
            const resultArea = document.getElementById('result-area');
            const spinner = document.getElementById('spinner');
            const fetchBtn = document.getElementById('fetchBtn');

            if (!urlInput) return;

            resultArea.style.display = 'none';
            spinner.style.display = 'block';
            fetchBtn.style.opacity = '0.6';
            fetchBtn.disabled = true;

            try {
                const response = await fetch('/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: urlInput })
                });

                const data = await response.json();

                spinner.style.display = 'none';
                fetchBtn.style.opacity = '1';
                fetchBtn.disabled = false;

                if (data.error) {
                    resultArea.innerHTML = `<div class="media-card" style="border-color: #e74c3c;"><p style="color: #e74c3c; text-align: center;">${data.error}</p></div>`;
                } else {
                    let videoButtons = '';
                    if (data.formats.video.length > 0) {
                        videoButtons = `<div class="quality-section-title">Video Qualities</div><div class="quality-grid">`;
                        data.formats.video.forEach(f => {
                            videoButtons += `<a href="${f.url}" target="_blank" class="quality-btn" download>${f.resolution}</a>`;
                        });
                        videoButtons += `</div>`;
                    }

                    let audioButtons = '';
                    if (data.formats.audio.length > 0) {
                        audioButtons = `<div class="quality-section-title">Audio Streams</div><div class="quality-grid">`;
                        data.formats.audio.forEach(f => {
                            audioButtons += `<a href="${f.url}" target="_blank" class="quality-btn" download>${f.quality}</a>`;
                        });
                        audioButtons += `</div>`;
                    }

                    resultArea.innerHTML = `
                        <div class="media-card">
                            <h3 class="media-title">${data.title}</h3>
                            ${videoButtons}
                            ${audioButtons}
                        </div>
                    `;
                }
                resultArea.style.display = 'block';
            } catch (err) {
                spinner.style.display = 'none';
                fetchBtn.style.opacity = '1';
                fetchBtn.disabled = false;
                resultArea.innerHTML = `<div class="media-card" style="border-color: #e74c3c;"><p style="color: #e74c3c; text-align: center;">Scan failed. Check link or try again.</p></div>`;
                resultArea.style.display = 'block';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/extract', methods=['POST'])
def extract_media():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Media File')
            raw_formats = info.get('formats', [])
            
            video_qualities = []
            audio_qualities = []
            seen_res = set()
            seen_audio = set()

            for f in raw_formats:
                f_url = f.get('url')
                if not f_url:
                    continue
                
                # Filter Video Formats (4K, 1080p, 720p, 480p, 360p)
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    height = f.get('height')
                    if height and height >= 360:
                        if height >= 2160: res_label = "4K Ultra HD"
                        elif height >= 1440: res_label = "1440p (2K)"
                        elif height >= 1080: res_label = "1080p Full HD"
                        elif height >= 720: res_label = "720p HD"
                        elif height >= 480: res_label = "480p"
                        else: res_label = "360p"
                        
                        if res_label not in seen_res:
                            seen_res.add(res_label)
                            video_qualities.append({'resolution': res_label, 'url': f_url})

                # Filter Audio Streams (320kbps, 128kbps, etc.)
                elif f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    abr = f.get('abr', 0)
                    if abr:
                        audio_label = f"{int(abr)} kbps Audio"
                        if audio_label not in seen_audio:
                            seen_audio.add(audio_label)
                            audio_qualities.append({'quality': audio_label, 'url': f_url})

            # Sort video highest to lowest resolution approximation
            video_qualities = sorted(video_qualities, key=lambda x: ('4K' in x['resolution'], '1440p' in x['resolution'], '1080p' in x['resolution'], '720p' in x['resolution']), reverse=True)

            return jsonify({
                'title': title,
                'formats': {
                    'video': video_qualities[:6],  # Top choices
                    'audio': audio_qualities[:4]
                }
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
