import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

async def ping_server(url, interval=600):
    """
    Periodically pings the given URL to keep the service awake.
    Default interval: 600 seconds (10 minutes).
    Render Free Tier sleeps after 15 minutes of inactivity.
    """
    if not url:
        return

    logger.info(f"Starting self-ping service for: {url}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.info("Self-ping successful.")
                    else:
                        logger.warning(f"Self-ping failed with status: {response.status}")
            except Exception as e:
                logger.error(f"Self-ping error: {e}")

            await asyncio.sleep(interval)
