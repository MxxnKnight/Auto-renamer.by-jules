from aiohttp import web
import logging

logger = logging.getLogger(__name__)

async def handle(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bot Status</title>
        <style>
            body {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background-color: #121212;
                color: #ffffff;
                font-family: Arial, sans-serif;
            }
            .container {
                text-align: center;
            }
            .status {
                font-size: 2rem;
                margin-bottom: 20px;
            }
            .pulse {
                width: 20px;
                height: 20px;
                background-color: #4CAF50;
                border-radius: 50%;
                display: inline-block;
                animation: pulse-animation 2s infinite;
                margin-left: 10px;
            }
            @keyframes pulse-animation {
                0% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7);
                }
                70% {
                    transform: scale(1);
                    box-shadow: 0 0 0 10px rgba(76, 175, 80, 0);
                }
                100% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(76, 175, 80, 0);
                }
            }
            .message {
                margin-top: 20px;
                color: #aaaaaa;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">
                Bot is Running <div class="pulse"></div>
            </div>
            <div class="message">
                Service is active and listening.
            </div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    return app
