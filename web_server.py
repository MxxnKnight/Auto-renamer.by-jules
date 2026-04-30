import os
import json
import logging
import time
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

def get_egress():
    if os.path.exists(EGRESS_FILE):
        try:
            with open(EGRESS_FILE, "r") as f:
                return json.load(f).get("used", 0)
        except: return 0
    return 0

def update_egress(bytes_sent):
    current = get_egress()
    with open(EGRESS_FILE, "w") as f:
        json.dump({"used": current + bytes_sent}, f)

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
        <style>
            body {{ background: #000; margin: 0; padding: 0; color: #fff; font-family: sans-serif; display: flex; flex-direction: column; height: 100vh; }}
            .header {{ padding: 12px; background: #111; text-align: center; font-size: 13px; color: #aaa; border-bottom: 1px solid #222; }}
            .main-content {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
            .plyr-container {{ width: 100%; max-width: 900px; padding: 10px; }}
            .notice {{ margin: 10px; padding: 10px; background: rgba(255,165,0,0.1); border: 1px solid rgba(255,165,0,0.3); border-radius: 8px; font-size: 12px; color: #ffa500; max-width: 800px; text-align: center; }}
            .footer {{ padding: 25px; background: #050505; text-align: center; }}
            .btn {{ display: inline-block; padding: 10px 20px; color: #fff; text-decoration: none; border-radius: 6px; font-weight: 500; font-size: 13px; cursor: pointer; border: none; }}
            .tools {{ margin-top: 15px; display: flex; gap: 8px; justify-content: center; }}
            .plyr {{ border-radius: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">Streaming: {file_name}</div>
        <div class="main-content">
            <div class="plyr-container">
                <video id="player" playsinline crossorigin="anonymous">
                    <source src="{stream_url}" type="video/mp4" />
                </video>
                <div class="tools">
                    <button onclick="takeSnapshot()" class="btn" style="background: #ff2e63;">📸 Frame</button>
                    <button onclick="copyTimestamp()" class="btn" style="background: #08d9d6;">⏱️ Time</button>
                    <button onclick="copyLink('{request.url.scheme}://{request.host}{stream_url}')" class="btn" style="background: #252a34;">📋 Raw Link</button>
                </div>
            </div>
            {"<div class='notice'>🎥 <b>Codec Warning:</b> This MKV uses HEVC/x265. If you see a black screen or it won't load, use the <b>VLC</b> button below.</div>" if is_mkv else ""}
        </div>
        <div class="footer">
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 15px;">
                <a href="{vlc_link}" class="btn" style="background: #ff8800; border: 1px solid #ff8800;">🧡 Watch in VLC</a>
                <a href="{mx_link}" class="btn" style="background: #00aaff; border: 1px solid #00aaff;">💙 MX Player</a>
            </div>
            <a href="{stream_url}" class="btn" style="background: transparent; border: 1px solid #333; color: #888;">📥 Download File</a>
        </div>
        <canvas id="snapshotCanvas" style="display:none;"></canvas>
        <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
        <script>
            const player = new Plyr('#player', {{
                controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'settings', 'pip', 'fullscreen'],
                ratio: '16:9'
            }});
            function takeSnapshot() {{
                const v = document.querySelector('video');
                const c = document.getElementById('snapshotCanvas');
                c.width = v.videoWidth; c.height = v.videoHeight;
                c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
                const l = document.createElement('a');
                l.download = 'frame.png'; l.href = c.toDataURL('image/png'); l.click();
            }}
            function copyTimestamp() {{
                const t = document.querySelector('video').currentTime;
                const fmt = new Date(t * 1000).toISOString().substr(11, 8);
                navigator.clipboard.writeText(fmt).then(() => alert('Time copied: ' + fmt));
            }}
            function copyLink(url) {{
                navigator.clipboard.writeText(url).then(() => alert('Link copied!'));
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
        'Content-Range': f'bytes {start}-{end}/{file_size}',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-cache' # Prevent browser from getting "stale" chunks
    }

    if not range_header:
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
    web_app = web.Application()
    web_app['bot_client'] = client
    web_app.router.add_get('/', handle_home)
    web_app.router.add_get('/view/{short_id}', stream_player_handler)
    web_app.router.add_get('/dl/{short_id}', raw_stream_handler)
    return web_app
