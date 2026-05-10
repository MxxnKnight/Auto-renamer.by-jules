import os
import json
import logging
import time
import asyncio
from aiohttp import web

logger = logging.getLogger(__name__)

# Persistent storage for file mappings
LINKS_FILE = "links.json"
EGRESS_FILE = "egress.json"

def load_links():
    if os.path.exists(LINKS_FILE):
        try:
            with open(LINKS_FILE, "r") as f:
                data = json.load(f)
                now = time.time()
                return {k: v for k, v in data.items() if now - v.get("time", 0) < 86400}
        except: return {}
    return {}

def save_links(file_map_data):
    with open(LINKS_FILE, "w") as f:
        json.dump(file_map_data, f)

file_map = load_links()

EGRESS_STATE = {"used": 0}

def init_egress():
    if os.path.exists(EGRESS_FILE):
        try:
            with open(EGRESS_FILE, "r") as f:
                EGRESS_STATE["used"] = json.load(f).get("used", 0)
        except: pass

init_egress()

def get_egress():
    return EGRESS_STATE["used"]

def update_egress(bytes_sent):
    EGRESS_STATE["used"] += bytes_sent

async def save_egress_task():
    while True:
        await asyncio.sleep(60)
        try:
            with open(EGRESS_FILE, "w") as f:
                json.dump(EGRESS_STATE, f)
        except: pass

async def handle_home(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bot Status</title>
        <style>
            body { display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #0f0f0f; color: #ffffff; font-family: 'Segoe UI', sans-serif; }
            .container { text-align: center; padding: 2.5rem; background: #1a1a1a; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.6); }
            .status { font-size: 1.6rem; margin-bottom: 15px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
            .pulse { width: 14px; height: 14px; background-color: #00ff88; border-radius: 50%; display: inline-block; animation: pulse-animation 2s infinite; margin-left: 12px; }
            @keyframes pulse-animation { 0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 12px rgba(0, 255, 136, 0); } 100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); } }
            .msg { color: #888; font-size: 0.95rem; letter-spacing: 0.5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">System Online <div class="pulse"></div></div>
            <div class="msg">Renamer Bot • High Precision Metadata</div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def stream_player_handler(request):
    short_id = request.match_info.get('short_id')
    if short_id not in file_map:
        return web.Response(text="Link Expired", status=404)

    data = file_map[short_id]
    if time.time() - data.get("time", 0) > 86400:
        file_map.pop(short_id, None)
        save_links(file_map)
        return web.Response(text="Link Expired (24h)", status=404)

    file_name = data["file_name"]
    stream_url = f"/dl/{short_id}"
    is_mkv = file_name.lower().endswith('.mkv')
    
    # Compatibility links
    vlc_link = f"vlc-http://{request.host}{stream_url}"
    mx_link = f"intent://{request.host}{stream_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{file_name}</title>
        <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-primary: #0a0a0c;
                --bg-secondary: #121216;
                --accent: #6c5ce7;
                --accent-hover: #8172e8;
                --text-main: #f1f1f1;
                --text-muted: #8b8b99;
                --danger: #ff4757;
                --warning: #ffa502;
                --success: #2ed573;
                --glass-bg: rgba(255, 255, 255, 0.03);
                --glass-border: rgba(255, 255, 255, 0.08);
            }}
            * {{ box-sizing: border-box; }}
            body {{ 
                background: radial-gradient(circle at 50% 0%, #1a1a24 0%, var(--bg-primary) 100%);
                margin: 0; padding: 0; color: var(--text-main); font-family: 'Inter', sans-serif;
                display: flex; flex-direction: column; min-height: 100vh;
            }}
            .header {{ 
                padding: 20px; text-align: center; font-size: 14px; font-weight: 500; color: var(--text-muted);
                background: var(--glass-bg); border-bottom: 1px solid var(--glass-border); backdrop-filter: blur(10px);
                word-break: break-word; line-height: 1.4;
            }}
            .header span {{ color: var(--text-main); font-weight: 600; }}
            .main-content {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px; }}
            .player-wrapper {{ 
                width: 100%; max-width: 1000px; padding: 15px; 
                background: var(--bg-secondary); border-radius: 20px; 
                box-shadow: 0 20px 50px rgba(0,0,0,0.5); border: 1px solid var(--glass-border);
            }}
            .plyr {{ border-radius: 12px; overflow: hidden; }}
            .plyr--video .plyr__control--overlaid {{ background: var(--accent); }}
            .plyr--video .plyr__control.plyr__tab-focus, .plyr--video .plyr__control:hover, .plyr--video .plyr__control[aria-expanded=true] {{ background: var(--accent); }}
            
            .tools {{ margin-top: 20px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
            .btn {{ 
                display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; 
                color: #fff; text-decoration: none; border-radius: 12px; font-weight: 600; font-size: 14px; 
                cursor: pointer; border: none; transition: all 0.3s ease;
                background: var(--glass-bg); border: 1px solid var(--glass-border);
            }}
            .btn:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); background: rgba(255,255,255,0.08); }}
            .btn-accent {{ background: linear-gradient(135deg, var(--accent), #5040d1); border: none; }}
            .btn-accent:hover {{ background: linear-gradient(135deg, var(--accent-hover), #6c5ce7); box-shadow: 0 8px 20px rgba(108, 92, 231, 0.4); }}
            
            .notice {{ 
                margin-top: 20px; padding: 16px 20px; background: rgba(255, 165, 2, 0.1); 
                border-left: 4px solid var(--warning); border-radius: 8px; font-size: 13px; color: #ffd32a; 
                max-width: 800px; display: flex; align-items: center; gap: 12px;
            }}
            .footer {{ 
                padding: 30px; background: #050505; border-top: 1px solid #111; 
                display: flex; flex-direction: column; align-items: center; gap: 20px;
            }}
            .ext-links {{ display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; }}
        </style>
    </head>
    <body>
        <div class="header">Now Streaming: <span>{file_name}</span></div>
        <div class="main-content">
            <div class="player-wrapper">
                <video id="player" playsinline crossorigin="anonymous">
                    <source src="{stream_url}" type="{data.get('mime_type', 'video/mp4')}" />
                </video>
                <div class="tools">
                    <button onclick="takeSnapshot()" class="btn">📸 Snapshot</button>
                    <button onclick="copyTimestamp()" class="btn">⏱️ Copy Time</button>
                    <button onclick="copyLink('{request.url.scheme}://{request.host}{stream_url}')" class="btn">🔗 Raw Link</button>
                </div>
            </div>
            {"<div class='notice'><div>⚠️</div><div><b>Format Warning:</b> You are attempting to stream an MKV file. Most web browsers do not natively support MKV or HEVC/x265 codecs. If the video fails to load or shows a black screen, please use the <b>Watch in VLC</b> button below.</div></div>" if is_mkv else ""}
        </div>
        <div class="footer">
            <div class="ext-links">
                <a href="{vlc_link}" class="btn" style="color: #ff8c00; border-color: rgba(255, 140, 0, 0.3);">🧡 Watch in VLC</a>
                <a href="{mx_link}" class="btn" style="color: #00a8ff; border-color: rgba(0, 168, 255, 0.3);">💙 Open in MX Player</a>
            </div>
            <a href="{stream_url}" class="btn btn-accent">📥 Download File</a>
        </div>
        <canvas id="snapshotCanvas" style="display:none;"></canvas>
        <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
        <script>
            const player = new Plyr('#player', {{
                controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'settings', 'pip', 'fullscreen'],
                ratio: '16:9',
                settings: ['quality', 'speed'],
                speed: {{ selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] }}
            }});
            
            function takeSnapshot() {{
                try {{
                    const v = document.querySelector('video');
                    const c = document.getElementById('snapshotCanvas');
                    c.width = v.videoWidth; c.height = v.videoHeight;
                    c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
                    const l = document.createElement('a');
                    l.download = 'snapshot-' + Math.floor(v.currentTime) + 's.png'; 
                    l.href = c.toDataURL('image/png'); l.click();
                }} catch (e) {{ alert('Snapshot failed. The video might not be fully loaded or has CORS restrictions.'); }}
            }}
            function copyTimestamp() {{
                const t = document.querySelector('video').currentTime;
                const fmt = new Date(t * 1000).toISOString().substring(11, 19);
                navigator.clipboard.writeText(fmt).then(() => alert('Timestamp copied: ' + fmt));
            }}
            function copyLink(url) {{
                navigator.clipboard.writeText(url).then(() => alert('Direct stream link copied!'));
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def raw_stream_handler(request):
    short_id = request.match_info.get('short_id')
    if short_id not in file_map:
        return web.Response(text="Invalid Link", status=404)

    data = file_map[short_id]
    if time.time() - data.get("time", 0) > 86400:
        file_map.pop(short_id, None)
        save_links(file_map)
        return web.Response(text="Link Expired", status=404)

    file_id = data["file_id"]
    file_name = data["file_name"]
    file_size = data["file_size"]
    mime_type = data["mime_type"]

    app = request.app['bot_client']
    range_header = request.headers.get('Range')
    start = 0
    end = file_size - 1

    if range_header:
        try:
            ranges = range_header.replace('bytes=', '').split('-')
            start = int(ranges[0])
            if ranges[1]: end = int(ranges[1])
        except: pass

    content_length = end - start + 1
    
    headers = {
        'Content-Type': mime_type,
        'Accept-Ranges': 'bytes',
        'Content-Length': str(content_length),
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        'Connection': 'keep-alive',
        'Access-Control-Expose-Headers': 'Content-Length, Content-Range'
    }

    if range_header:
        headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    else:
        headers['Content-Disposition'] = f'attachment; filename="{file_name}"'

    response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
    await response.prepare(request)

    try:
        # Optimized chunk size for Render/Telegram stability (2MB)
        async for chunk in app.stream_media(file_id, offset=start, limit=content_length):
            await response.write(chunk)
            update_egress(len(chunk))
    except Exception as e:
        logger.error(f"Stream interrupted: {e}")
    finally:
        await response.write_eof()
    
    return response

async def start_web_server(client):
    asyncio.create_task(save_egress_task())
    web_app = web.Application()
    web_app['bot_client'] = client
    web_app.router.add_get('/', handle_home)
    web_app.router.add_get('/view/{short_id}', stream_player_handler)
    web_app.router.add_get('/dl/{short_id}', raw_stream_handler)
    return web_app
