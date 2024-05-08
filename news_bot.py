import asyncio
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import newspaper
from newspaper import Article, ArticleException
from typing import List
from urllib.parse import urlparse, urljoin, quote

cred = credentials.Certificate("knowledgebot-44a23-firebase-adminsdk-bdrpk-12b96d1732.json")
app = firebase_admin.initialize_app(cred)

db = firestore.client()

NEWSPAPERS = [
    # "https://www.lesechos.fr/",
    # "http://www.lemonde.fr",
    # "https://www.liberation.fr/",
    # "https://www.lexpress.fr/",
    "https://www.humanite.fr/",
    # "https://usbeketrica.com/",
    # "https://next.ink/",
    # "https://www.ladn.eu/",
    # "https://www.leparisien.fr/",
    # "https://www.mediapart.fr/",
    # "https://www.latribune.fr/",
    # "https://www.lepoint.fr/",
]
SCHEMA_FIELDS = {
    "author": "NULL", 
    "is_about_ai": "NULL", 
    "parse_result": "NULL"}
KEYWORDS_AI = [" ia ", "intelligence artificielle", "machine learning", "reseaux de neurones"]

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0'
NEWSPAPER_CONFIG = newspaper.Config()
NEWSPAPER_CONFIG.browser_user_agent = USER_AGENT

def clean_url(url: str) -> str:
    return urljoin(url, urlparse(url).geturl())

async def get_urls_newspapers() -> List[str]:
    """Sources article links from the newspaper library"""
    articles_urls = []
    for source in NEWSPAPERS:
        paper = newspaper.build(source, memoize_articles=False, config=NEWSPAPER_CONFIG)
        articles_urls.extend([
            clean_url(article.url) for article in paper.articles])
    return articles_urls

# async def fetch_urls(api_url):
#     async with aiohttp.ClientSession() as session:
#         async with session.get(api_url) as response:
#             if response.status == 200:
#                 urls = await response.json()
#                 return urls
#             else:
#                 print("Failed to fetch URLs")
#                 return []

def update_documents_with_new_schema():
    collection_ref = db.collection('articles')
    # Fetch documents in batches (to avoid memory issues with large collections)
    for document in collection_ref.limit(500).stream():
        update_required = False
        update_data = {}
        for field, default_value in SCHEMA_FIELDS.items():
            # Check if the document is missing any of the new schema fields
            if field not in document.to_dict():
                update_required = True
                update_data[field] = default_value
        if update_required:
            # Run the update in a separate thread to avoid blocking
            document.reference.update(update_data)
            print(f"Updated document {document.id} with new schema fields.")

async def add_article_if_not_exists(url):
    encoded_url = quote(url, safe='')
    doc_ref = db.collection('articles').document(encoded_url)
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({
            'url': url,
            'added_on': firestore.SERVER_TIMESTAMP,  # Placeholder data
            **SCHEMA_FIELDS
        })
        print(f"Added article with URL: {url}")

async def is_about_ai():
    while True:
        documents = db.collection('articles').where(
            'is_about_ai', '==', "NULL").where(
                "parse_result", "!=", "NULL").stream()
        for document in documents:
            text = document.get("parse_result").get("text")
            if any(keyword in text.lower() for keyword in KEYWORDS_AI):
                document.reference.update(
                    {
                        "is_about_ai": True
                    }
                )
            else:
                document.reference.update(
                    {
                        "is_about_ai": False
                    }
                )
        await asyncio.sleep(1)

async def parse_articles():
    while True:
        documents = db.collection('articles').where(
            'parse_result', '==', "NULL").stream()
        for document in documents:
            url = document.get("url")
            article = Article(url)
            try:
                article.download()
                article.parse()
            
                document.reference.update(
                    {
                        "parse_result": {
                            "authors": article.authors,
                            "title": article.title,
                            "text": article.text,
                            "error": None
                        }
                    }
                )
            except ArticleException as e:
                document.reference.update(
                    {
                        "parse_result": {
                            "authors": [],
                            "title": "",
                            "text": "",
                            "error": str(e)
                        }
                    }
                )
        
            print("Parsed article")
        await asyncio.sleep(1)

async def populate_missing_authors():
    while True:
        articles = db.collection('articles').where('author', '==', "NULL").stream()
        for article in articles:
            # Logic to determine the author...
            author_name = "Some Author"  # Placeholder for the logic to find the author's name
            article.reference.update({'author': author_name})
            print(f"Updated article {article.id} with author {author_name}")
        await asyncio.sleep(1)  # Check for missing authors every 5 minutes

async def fetch_and_add_urls():
    while True:
        urls = await get_urls_newspapers()
        for url in urls:
            await add_article_if_not_exists(url)
        await asyncio.sleep(1)  # Wait for 1 seconds before fetching again

async def main():
    await asyncio.gather(
        fetch_and_add_urls(),
        populate_missing_authors(),
        parse_articles(),
        is_about_ai()
    )

if __name__ == "__main__":
    update_documents_with_new_schema()
    asyncio.run(main())