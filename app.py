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
    <title>VELOX — Media Downloader</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-obsidian: #07080c;
            --card-glass: rgba(14, 16, 23, 0.8);
            --gold-accent: #f1c40f;
            --gold-bright: #f39c12;
            --gold-gradient: linear-gradient(135deg, #f39c12, #f1c40f, #d4af37);
            --text-main: #f4f5f7;
            --text-muted: #8e92a4;
            --border-glass: rgba(241, 196, 15, 0.2);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        body {
            background-color: var(--bg-obsidian);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 50% -20%, rgba(241, 196, 15, 0.12), transparent 60%),
                radial-gradient(circle at 50% 120%, rgba(243, 156, 18, 0.05), transparent 50%);
        }

        /* Butter-smooth entry animation */
        @keyframes containerEntrance {
            0% {
                opacity: 0;
                transform: translateY(40px) scale(0.96);
                filter: blur(10px);
            }
            100% {
                opacity: 1;
                transform: translateY(0) scale(1);
                filter: blur(0);
            }
        }

        /* Live butter-smooth breathing gold glow animation */
        @keyframes butterGoldGlow {
            0% {
                border-color: rgba(241, 196, 15, 0.4);
                box-shadow: 0 0 15px rgba(241, 196, 15, 0.15), inset 0 0 10px rgba(241, 196, 15, 0.05);
            }
            50% {
                border-color: rgba(243, 156, 18, 0.9);
                box-shadow: 0 0 35px rgba(241, 196, 15, 0.45), inset 0 0 15px rgba(243, 156, 18, 0.2);
            }
            100% {
                border-color: rgba(241, 196, 15, 0.4);
                box-shadow: 0 0 15px rgba(241, 196, 15, 0.15), inset 0 0 10px rgba(241, 196, 15, 0.05);
            }
        }

        @keyframes cardReveal {
            from {
                opacity: 0;
                transform: translateY(15px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .container {
            width: 100%;
            max-width: 600px;
            background: var(--card-glass);
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            border: 1px solid var(--border-glass);
            border-radius: 28px;
            padding: 45px 35px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.7);
            animation: containerEntrance 0.9s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .header {
            text-align: center;
            margin-bottom: 35px;
        }

        .logo-title {
            font-size: 2.8rem;
            font-weight: 700;
            background: var(--gold-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 3px;
            margin-bottom: 6px;
            text-transform: uppercase;
        }

        .subtitle {
            color: var(--text-muted);
            font-size: 0.95rem;
            font-weight: 400;
            letter-spacing: 0.5px;
        }

        .input-group {
            position: relative;
            margin-bottom: 25px;
        }

        .url-input {
            width: 100%;
            padding: 20px 22px;
            background: rgba(7, 8, 12, 0.85);
            border: 1.5px solid rgba(241, 196, 15, 0.25);
            border-radius: 16px;
            color: #fff;
            font-size: 1rem;
            outline: none;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.5);
        }

        .url-input:focus, .url-input:hover {
            animation: butterGoldGlow 3s infinite ease-in-out;
        }

        .btn-submit {
            width: 100%;
            padding: 18px;
            background: var(--gold-gradient);
            border: none;
            border-radius: 16px;
            color: #07080c;
            font-weight: 700;
            font-size: 1.05rem;
            cursor: pointer;
            letter-spacing: 0.8px;
            box-shadow: 0 10px 30px rgba(241, 196, 15, 0.25);
        }

        .btn-submit:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(241, 196, 15, 0.45);
        }

        .btn-submit:active {
            transform: translateY(1px);
        }

        #result-area {
            margin-top: 25px;
            display: none;
            animation: cardReveal 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .media-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(241, 196, 15, 0.2);
            border-radius: 18px;
            padding: 22px;
            text-align: center;
        }

        .media-title {
            font-size: 1.05rem;
            margin-bottom: 18px;
            color: #fff;
            line-height: 1.5;
        }

        .download-link {
            display: inline-block;
            padding: 14px 28px;
            background: rgba(241, 196, 15, 0.12);
            border: 1px solid var(--gold-accent);
            color: var(--gold-accent);
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
        }

        .download-link:hover {
            background: var(--gold-gradient);
            color: #07080c;
            box-shadow: 0 5px 20px rgba(241, 196, 15, 0.4);
        }

        .spinner {
            display: none;
            width: 34px;
            height: 34px;
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

    <div class="container">
        <div class="header">
            <h1 class="logo-title">VELOX</h1>
            <p class="subtitle">Next-Generation High-Speed Media Downloader</p>
        </div>

        <div class="input-group">
            <input type="text" id="urlInput" class="url-input" placeholder="Paste media link here..." autocomplete="off">
        </div>

        <button id="fetchBtn" class="btn-submit" onclick="fetchMedia()">Get Download Link</button>

        <div id="spinner" class="spinner"></div>

        <div id="result-area"></div>
    </div>

    <script>
        async function fetchMedia() {
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
                    resultArea.innerHTML = `<div class="media-card" style="border-color: #e74c3c;"><p style="color: #e74c3c;">${data.error}</p></div>`;
                } else {
                    resultArea.innerHTML = `
                        <div class="media-card">
                            <h3 class="media-title">${data.title}</h3>
                            <a href="${data.download_url}" target="_blank" class="download-link" download>Download Media</a>
                        </div>
                    `;
                }
                resultArea.style.display = 'block';
            } catch (err) {
                spinner.style.display = 'none';
                fetchBtn.style.opacity = '1';
                fetchBtn.disabled = false;
                resultArea.innerHTML = `<div class="media-card" style="border-color: #e74c3c;"><p style="color: #e74c3c;">Extraction failed. Check link or try again.</p></div>`;
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
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Media File')
            download_url = info.get('url')
            
            return jsonify({
                'title': title,
                'download_url': download_url
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
