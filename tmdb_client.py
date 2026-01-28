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
            logger.info("TMDB Integration Enabled.")
        else:
            logger.warning("TMDB_API_KEY not set. TMDB enrichment disabled.")

    def search_media(self, query, year=None, is_series=False):
        if not self.api_key or not query:
            return None

        logger.info(f"TMDB Search Query: '{query}' (Year: {year}, IsSeries: {is_series})")

        try:
            results = []
            if is_series:
                results = self.tv_api.search(query)
            else:
                results = self.movie_api.search(query)

            if not results:
                logger.info("TMDB: No results found.")
                return None

            # Filter/Find best match
            results_list = list(results)
            best_match = results_list[0]

            # Check if best_match is a string (indicates malformed result or iterating keys)
            if isinstance(best_match, str):
                logger.warning(f"TMDB returned a string '{best_match}' instead of an object. Likely iterating keys of a malformed response.")
                return None

            # If year provided, try to find exact year match in top results
            if year:
                for res in results_list[:3]: # Check top 3
                    # Safety check if res is dict or object
                    if isinstance(res, dict):
                         res_date = res.get('release_date') or res.get('first_air_date') or ''
                    else:
                         res_date = getattr(res, 'release_date', getattr(res, 'first_air_date', ''))

                    if res_date and str(year) in str(res_date):
                        best_match = res
                        logger.info(f"TMDB: Found year match: {res_date}")
                        break

            # Safely extract attributes whether it's an object or dict
            def get_attr(obj, attr, alt_attr=None):
                val = None
                if isinstance(obj, dict):
                    val = obj.get(attr)
                    if not val and alt_attr:
                        val = obj.get(alt_attr)
                else:
                    val = getattr(obj, attr, None)
                    if val is None and alt_attr:
                        val = getattr(obj, alt_attr, None)

                # Prevent returning methods (e.g. str.title)
                if callable(val):
                    return None

                return val if val is not None else ''

            title = get_attr(best_match, 'title', 'name')
            res_date = get_attr(best_match, 'release_date', 'first_air_date')

            # Handle year parsing safely
            res_year = year
            if res_date and isinstance(res_date, str) and '-' in res_date:
                try:
                    res_year = int(res_date.split('-')[0])
                except ValueError:
                    pass

            result_data = {
                "title": title,
                "year": res_year,
                "overview": get_attr(best_match, 'overview'),
                "id": get_attr(best_match, 'id')
            }
            logger.info(f"TMDB Success: Found '{title}' ({res_year})")
            return result_data

        except Exception as e:
            logger.error(f"TMDB Search Error: {e}", exc_info=True)
            return None
