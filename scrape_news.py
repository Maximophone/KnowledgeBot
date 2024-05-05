from news.scraper import get_all_ai_articles, extract_authors
import asyncio

async def retrieve_newspapers():
    while True:
        pass

if __name__ == "__main__":
    get_all_ai_articles("news/extracted")
    extract_authors("news/extracted")
    