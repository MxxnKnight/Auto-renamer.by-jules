import os
import logging
from tmdbv3api import TMDb, Movie, TV

logger = logging.getLogger(__name__)

class TMDBClient:
    def __init__(self):
        self.api_key = os.getenv("TMDB_API_KEY")
        self.tmdb = TMDb()
        if self.api_key:
            self.tmdb.api_key = self.api_key
            self.tmdb.language = 'en'
            self.movie_api = Movie()
            self.tv_api = TV()
        else:
            logger.warning("TMDB_API_KEY not set. TMDB enrichment disabled.")

    def search_media(self, query, year=None, is_series=False):
        if not self.api_key or not query:
            return None

        try:
            results = []
            if is_series:
                results = self.tv_api.search(query)
            else:
                results = self.movie_api.search(query)

            if not results:
                return None

            # Filter/Find best match
            best_match = results[0]

            # If year provided, try to find exact year match in top results
            if year:
                for res in results[:3]: # Check top 3
                    res_date = getattr(res, 'release_date', getattr(res, 'first_air_date', ''))
                    if res_date and str(year) in res_date:
                        best_match = res
                        break

            title = getattr(best_match, 'title', getattr(best_match, 'name', ''))
            res_date = getattr(best_match, 'release_date', getattr(best_match, 'first_air_date', ''))
            res_year = int(res_date.split('-')[0]) if res_date else year

            return {
                "title": title,
                "year": res_year,
                "overview": getattr(best_match, 'overview', ''),
                "id": best_match.id
            }

        except Exception as e:
            logger.error(f"TMDB Search Error: {e}")
            return None
