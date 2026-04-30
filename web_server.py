import os
import json
import logging
from aiohttp import web

logger = logging.getLogger(__name__)

# Temporary storage for file mappings
file_map = {}

# Egress tracking file
EGRESS_FILE = "egress.json"

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
            body { display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #121212; color: #ffffff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            .container { text-align: center; padding: 2rem; background: #1e1e1e; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            .status { font-size: 1.5rem; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; }
            .pulse { width: 12px; height: 12px; background-color: #4CAF50; border-radius: 50%; display: inline-block; animation: pulse-animation 2s infinite; margin-left: 10px; }
            @keyframes pulse-animation { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); } }
            .msg { color: #888; font-size: 0.9rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">Renamer Bot is Active <div class="pulse"></div></div>
            <div class="msg">Precision processing enabled.</div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def stream_player_handler(request):
    short_id = request.match_info.get('short_id')
    if short_id not in file_map:
        return web.Response(text="File Not Found", status=404)

    data = file_map[short_id]
    file_name = data["file_name"]
    stream_url = f"/dl/{short_id}"
    is_mkv = file_name.lower().endswith('.mkv')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Streaming: {file_name}</title>
        <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
        <style>
            body {{ background: #000; margin: 0; padding: 0; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; height: 100vh; }}
            .header {{ padding: 15px; background: #111; text-align: center; font-size: 14px; border-bottom: 1px solid #222; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}
            .main-content {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; }}
            .plyr-container {{ width: 100%; max-width: 1000px; padding: 10px; box-sizing: border-box; }}
            .notice {{ margin-top: 15px; color: #ffa500; font-size: 13px; text-align: center; padding: 0 20px; }}
            .footer {{ padding: 20px; background: #000; text-align: center; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #007bff; color: #fff; text-decoration: none; border-radius: 8px; font-weight: bold; transition: background 0.2s; }}
            .btn:hover {{ background: #0056b3; }}
            /* Fix Plyr scaling issues */
            .plyr {{ border-radius: 8px; overflow: hidden; }}
        </style>
    </head>
    <body>
        <div class="header">🍿 {file_name}</div>
        <div class="main-content">
            <div class="plyr-container">
                <video id="player" playsinline controls>
                    <source src="{stream_url}" type="video/mp4" />
                </video>
            </div>
            {"<div class='notice'>⚠️ <b>Note:</b> MKV files may not play in some browsers. If it's stuck, please use the button below to open in <b>VLC</b> or <b>MX Player</b>.</div>" if is_mkv else ""}
        </div>
        <div class="footer">
            <div style="margin-bottom: 15px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                <a href="vlc://{request.url.scheme}://{request.host}{stream_url}" class="btn" style="background: #ff8800;">🧡 VLC</a>
                <a href="intent://{request.host}{stream_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end" class="btn" style="background: #00aaff;">💙 MX Player</a>
                <button onclick="copyLink('{request.url.scheme}://{request.host}{stream_url}')" class="btn" style="background: #28a745; border: none; cursor: pointer;">📋 Copy Link</button>
            </div>
            <a href="{stream_url}" class="btn" style="background: #6c757d; width: 100%; max-width: 300px;">📥 Direct Download</a>
        </div>
        <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
        <script>
            const player = new Plyr('#player', {{
                controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                ratio: '16:9'
            }});
            function copyLink(url) {{
                navigator.clipboard.writeText(url).then(() => {{
                    alert('Stream link copied to clipboard!');
                }});
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
    }

    if not range_header:
        headers['Content-Disposition'] = f'attachment; filename="{file_name}"'

    response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
    await response.prepare(request)

    try:
        async for chunk in app.stream_media(file_id, offset=start, limit=content_length):
            await response.write(chunk)
            update_egress(len(chunk))
    except Exception as e:
        logger.error(f"Stream error: {e}")
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
