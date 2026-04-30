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
            logger.info("TMDB Precision Client Enabled.")
        else:
            logger.warning("TMDB_API_KEY not set.")

    async def search_media(self, query, year_hint=None, is_series=False):
        if not self.api_key or not query:
            return None

        endpoint = "/search/tv" if is_series else "/search/movie"
        
        # Pass 1: Search with year_hint if provided
        params = {"api_key": self.api_key, "query": query, "language": self.language}
        if year_hint:
            params["year" if not is_series else "first_air_date_year"] = year_hint

        logger.info(f"TMDB Search: '{query}' (Hint: {year_hint})")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        
                        # If we have results with the year hint, pick the best one
                        if results:
                            best = self._pick_best_match(results, year_hint, is_series)
                            if best: return best

                # Pass 2: Search WITHOUT year hint (if Pass 1 failed or if year was wrong)
                if year_hint:
                    logger.info(f"TMDB: No results with year {year_hint}. Retrying without year...")
                    params.pop("year" if not is_series else "first_air_date_year", None)
                    async with session.get(f"{self.base_url}{endpoint}", params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            if results:
                                return self._pick_best_match(results, year_hint, is_series)

        except Exception as e:
            logger.error(f"TMDB Error: {e}")
        return None

    def _pick_best_match(self, results, year_hint, is_series):
        # Priority 1: Exact Year Match
        if year_hint:
            for res in results:
                res_date = res.get("first_air_date") if is_series else res.get("release_date")
                if res_date:
                    try:
                        res_year = int(res_date.split("-")[0])
                        if res_year == int(year_hint):
                            return self._format_result(res, is_series)
                    except: pass
        
        # Priority 2: Most Popular (highest popularity)
        # Results from TMDB search are already sorted by relevance, but we can double check
        sorted_results = sorted(results, key=lambda x: x.get("popularity", 0), reverse=True)
        return self._format_result(sorted_results[0], is_series)

    def _format_result(self, res, is_series):
        title = res.get("name") if is_series else res.get("title")
        res_date = res.get("first_air_date") if is_series else res.get("release_date")
        res_year = None
        if res_date:
            try: res_year = int(res_date.split("-")[0])
            except: pass
        
        return {
            "title": title,
            "year": res_year,
            "id": res.get("id")
        }
