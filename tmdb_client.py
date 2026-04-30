import os
import logging
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

class TMDBClient:
    def __init__(self):
        self.api_key = os.getenv("TMDB_API_KEY")
        self.base_url = "https://api.themoviedb.org/3"
        self.language = "en-US"
        if self.api_key:
            logger.info("TMDB Integration Enabled (Async).")
        else:
            logger.warning("TMDB_API_KEY not set. TMDB enrichment disabled.")

    async def search_media(self, query, year=None, is_series=False):
        if not self.api_key or not query:
            return None

        endpoint = "/search/tv" if is_series else "/search/movie"
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": self.language
        }
        if year:
            params["year" if not is_series else "first_air_date_year"] = year

        logger.info(f"TMDB Search ({'TV' if is_series else 'Movie'}): '{query}' (Year: {year})")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as response:
                    if response.status != 200:
                        logger.error(f"TMDB API Error: {response.status}")
                        return None
                    
                    data = await response.json()
                    results = data.get("results", [])
                    
                    if not results:
                        # Fallback: Try without year if no results found with year
                        if year:
                            logger.info(f"TMDB: No results with year {year}. Retrying without year...")
                            params.pop("year" if not is_series else "first_air_date_year", None)
                            async with session.get(f"{self.base_url}{endpoint}", params=params) as retry_response:
                                if retry_response.status == 200:
                                    data = await retry_response.json()
                                    results = data.get("results", [])
                    
                    if not results:
                        return None

                    # Pick the first result
                    best_match = results[0]
                    
                    title = best_match.get("name") if is_series else best_match.get("title")
                    res_date = best_match.get("first_air_date") if is_series else best_match.get("release_date")
                    
                    res_year = None
                    if res_date:
                        try:
                            res_year = int(res_date.split("-")[0])
                        except (ValueError, IndexError):
                            pass

                    return {
                        "title": title,
                        "year": res_year or year,
                        "overview": best_match.get("overview"),
                        "id": best_match.get("id")
                    }

        except Exception as e:
            logger.error(f"TMDB Search Error: {e}", exc_info=True)
            return None
