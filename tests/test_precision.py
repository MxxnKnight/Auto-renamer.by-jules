import asyncio
import os
from tmdb_client import TMDBClient
from dotenv import load_dotenv

load_dotenv()

async def test_precision():
    tmdb = TMDBClient()
    
    test_cases = [
        # Wrong year case
        {"query": "Inception", "year": 2012, "is_series": False}, # Correct is 2010
        # Duplicate name case (Old vs New)
        {"query": "The Lion King", "year": 1994, "is_series": False},
        {"query": "The Lion King", "year": 2019, "is_series": False},
        # Series case
        {"query": "One Piece", "year": 1999, "is_series": True}
    ]

    print("Running Precision TMDB Tests...\n")
    for case in test_cases:
        res = await tmdb.search_media(case["query"], case["year"], case["is_series"])
        if res:
            print(f"Query: {case['query']} ({case['year']}) -> Found: {res['title']} ({res['year']})")
        else:
            print(f"Query: {case['query']} ({case['year']}) -> Not Found")
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(test_precision())
