import asyncio
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import newspaper
from newspaper import Article, ArticleException
from typing import List, Dict, Any
from dataclasses import asdict
from urllib.parse import urlparse, urljoin, quote

from lxml import etree

from news.news_utils import get_article_text, get_source, NEWS_SOURCES
from ai import AI

from news.question import Answer, answer_question, multi_answer_question

haiku = AI("haiku")
gemini = AI("gemini1.5")

cred = credentials.Certificate("knowledgebot-44a23-firebase-adminsdk-bdrpk-12b96d1732.json")
app = firebase_admin.initialize_app(cred)

db = firestore.client()

NEWSPAPERS = [
    "https://www.lesechos.fr/",
    "http://www.lemonde.fr",
    "https://www.liberation.fr/",
    "https://www.lexpress.fr/",
    "https://www.humanite.fr/",
    "https://usbeketrica.com/",
    "https://next.ink/",
    "https://www.ladn.eu/",
    "https://www.leparisien.fr/",
    "https://www.mediapart.fr/",
    "https://www.latribune.fr/",
    "https://www.lepoint.fr/",
]
SCHEMA_FIELDS = {
    #"author": "DELETE", 
    "filter_url": "v0",
    "is_about_ai": "v0", 
    "parse_result": "v1",
    "authors_extraction": "v0",
    "question1": "v0",
    "question2": "v0",
    "question3": "v0",
    "question4": "v0",
    "question5": "v0",
    "question6": "v0",
    "question7": "v0",
    "question8": "v0",
    "question9": "v0",
    "question10": "v0",
    }
DEFAULT_VALUE = "NULL"
KEYWORDS_AI = [" ia ", "intelligence artificielle", "machine learning", "reseaux de neurones"]
URLS_FILE = "news/extracted/urls.txt"

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0'
NEWSPAPER_CONFIG = newspaper.Config()
NEWSPAPER_CONFIG.browser_user_agent = USER_AGENT

PROMPT = """Find the names of all the authors in the following article. There can be one or several authors. They should all be listed at the same place in the text, either towards the begining or towards the end. Return the result in the following form:
<authors>
    <author>First Author</author>
    ...
</authors>

"""

QUESTION_1 = "On a scale from 1 to 5, how concerned is the author about catastrophic risk from articifial intelligence? 1 being not concerned at all, and 5 extremely concerned. The answer should only be a number, no text."
QUESTION_2 = "On a scale from 1 to 5, how much is Artificial Intelligence at the center of this article? 1 being not central at all or not even mentioned, and 5 if it is the main topic. The answer should only be a number, no text."

QUESTION_URL = "On a scale from 1 to 5, how likely is it that this URL links to an article talking about Artificial Intelligence? If the URL contains no information, it is probably not about AI, go for 1. The answer should only be a number, no text."

THRESHOLD_FILTER_URL = 3 # we only keep articles above or equal to this

CACHED_DOCUMENT_IDS = set()

def clean_url(url: str) -> str:
    return urljoin(url, urlparse(url).geturl())

def uri_validator(x):
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False
    
def update_doc(document, field_name: str, data: Dict[str, Any]):
    assert field_name in SCHEMA_FIELDS, f"Field {field_name} not in schema"
    document.reference.update(
        {
            field_name: data,
            f"{field_name}_version": SCHEMA_FIELDS[field_name]
        }
    )

def update_null_fields(field_name: str, in_loop_wait=0.5, 
                       out_loop_wait=1, batch: int = None):
    def decorator(job):
        async def inner():
            while True:
                query = db.collection("articles").where(
                    field_name, "==", "NULL")
                documents = query.get()
                print(f"Looping {field_name}: {len(documents)} documents.")
                if batch is None:
                    for document in documents:
                        if in_loop_wait:
                            await asyncio.sleep(in_loop_wait)
                        print(f"    Handling {field_name} on document {document.get('url')[8:40]}")
                        data = await job(document)
                        # if data is None, we don't update
                        if data is not None:
                            update_doc(document, field_name, data)
                else:
                    if len(documents) > 0:
                        i = 0
                        for i in range(len(documents)//batch + 1):
                            batch_docs = documents[i*batch:(i+1)*batch]
                            if in_loop_wait:
                                await asyncio.sleep(in_loop_wait)
                                print(f"    Handling {field_name} on document batch")
                                datas = await job(batch_docs)
                                assert len(datas) == len(batch_docs)
                                for data, document in zip(datas, batch_docs):
                                    if data is not None:
                                        update_doc(document, field_name, data)
                if out_loop_wait:
                    await asyncio.sleep(out_loop_wait)
        return inner
    return decorator

async def get_urls_newspapers() -> List[str]:
    """Sources article links from the newspaper library"""
    articles_urls = []
    for source in NEWS_SOURCES:
        # paper = await asyncio.to_thread(newspaper.build, source, {
        #     "memoize_articles": False,
        #     "config": NEWSPAPER_CONFIG
        # })
        paper = newspaper.build(source.url, memoize_articles=False, config=NEWSPAPER_CONFIG)
        articles_urls.extend([
            clean_url(article.url) for article in paper.articles])
        await asyncio.sleep(10)
    return articles_urls

def update_documents_with_new_schema():
    """and build cache"""
    collection_ref = db.collection('articles')
    # Fetch documents in batches (to avoid memory issues with large collections)
    # TODO: Check this, this may be wrong
    for document in collection_ref.stream():
        CACHED_DOCUMENT_IDS.add(document.id)
        update_required = False
        update_data = {}
        for field, version in SCHEMA_FIELDS.items():
            # Check if the document is missing any of the new schema fields
            doc_dict = document.to_dict()
            if field in doc_dict and doc_dict.get(f"{field}_version") == version:
                # This one does not need to be updated
                continue
            update_required = True
            update_data[field] = DEFAULT_VALUE if version != "DELETE" else firestore.DELETE_FIELD
            update_data[f"{field}_version"] = version if version != "DELETE" else firestore.DELETE_FIELD
        if update_required:
            # Run the update in a separate thread to avoid blocking
            document.reference.update(update_data)
            print(f"Updated document {document.id} with new schema fields.")

async def add_article_if_not_exists(url):
    if not uri_validator(url):
        # invalid url
        return
    encoded_url = quote(url, safe='')
    if not encoded_url in CACHED_DOCUMENT_IDS:
        doc_ref = db.collection('articles').document(encoded_url)
        doc_ref.set({
            'url': url,
            'added_on': firestore.SERVER_TIMESTAMP,  # Placeholder data
            **{field:"NULL" for field in SCHEMA_FIELDS},
            **{f"{field}_version": version for field, version in SCHEMA_FIELDS.items()}
        })
        CACHED_DOCUMENT_IDS.add(encoded_url)
        print(f"Added article with URL: {url}")

async def question(field_name, question):
    while True:
        query = db.collection("articles").where(
            field_name, "==", "NULL")
        documents = query.get()
        print(f"Looping {field_name}: {len(documents)} documents.")
        for document in documents:
            is_about_ai = document.get("is_about_ai")
            if is_about_ai == "NULL":
                return
            if is_about_ai:
                await asyncio.sleep(1)
                print(f"    Handling {field_name} on document {document.get('url')[8:40]}")
                parse_result = document.get("parse_result")
                if parse_result == "NULL":
                    continue
                text = parse_result.get("article_text")
                if text:
                    answer = answer_question(text, question, model=haiku)
                else:
                    answer = Answer(
                        error=True, 
                        error_message = "No article text in parse_result") 
                update_doc(document, field_name, asdict(answer))
        await asyncio.sleep(1)

@update_null_fields("filter_url")
async def filter_url_OLD(document):
    url = document.get("url")
    answer = answer_question(url, QUESTION_URL, model=haiku)
    print("------------------")
    print(url)
    print(answer.answer)
    print(answer.reflexions)
    print(answer.explanations)
    print("------------------")
    try:
        value = int(answer.answer)
    except ValueError:
        value = 0
    return value

@update_null_fields("filter_url", batch=8)
async def filter_url(doc_batch):
    urls = [doc.get("url") for doc in doc_batch]
    multi_answer = multi_answer_question(urls, QUESTION_URL, model=haiku)
    print("------------------")
    values = []
    for i, answer in enumerate(multi_answer.answers):
        print(f"{answer} - {urls[i]}")
        try:
            value = int(answer)
        except ValueError:
            value = 0
        values.append(value)
    print(multi_answer.reflexions)
    print(multi_answer.explanations)
    if multi_answer.error:
        print("ERROR")
        print(multi_answer.full_answer)
        values = ["NULL"] * len(doc_batch)
    print("------------------")
    return values

@update_null_fields("authors_extraction", in_loop_wait=0.1)
async def extract_authors(document) -> Dict[str, Any]:
    parse_result = document.get("parse_result")
    if parse_result == "NULL":
        return None
    if document.get("is_about_ai") == "NULL":
        return None
    if not document.get("is_about_ai"):
        return {}
    await asyncio.sleep(0.5)
    text = parse_result.get("article_text")
    if not text:
        return {
            "authors": [],
            "error": "No article text in parse_result"
        }
    response = haiku.message(PROMPT + text)
    try:
        tree = etree.ElementTree(etree.fromstring("<response>" + response + "</response>"))
    except etree.XMLSyntaxError:
        return {
            "authors": [],
            "error": f"LLM returned invalid XML: {response}"
        }
    if not tree.find("authors"):
        return {
            "authors": [],
            "error": f"LLM did not return an <authors> tag. LLM's response: {response}"
        }
    authors = [x.text for x in tree.find("authors").findall("author")]
    return {"authors": authors,"error": None}

@update_null_fields("is_about_ai")
async def is_about_ai(document) -> bool:
    if document.get("filter_url") == "NULL":
        return
    if document.get("filter_url") < THRESHOLD_FILTER_URL:
        return False
    if document.get("parse_result") == "NULL":
        return
    text = document.get("parse_result").get("text")
    return any(keyword in text.lower() for keyword in KEYWORDS_AI)

@update_null_fields("parse_result")
async def parse_articles(document):
    if document.get("filter_url") == "NULL":
        return
    if document.get("filter_url") < THRESHOLD_FILTER_URL:
        # we don't parse
        return {}
    url = document.get("url")
    article = Article(url)
    source = get_source(url)
    data = {
        "source": source.name if source else None,
        "source_url": source.url if source else None
    }
    try:
        #await asyncio.to_thread(article.download)
        #await asyncio.to_thread(article.parse)
        article.download()
        article.parse()
        data.update({
            "authors": article.authors,
            "title": article.title,
            "text": article.text,
            "article_text": get_article_text(article) if source else None,
            "error": None
        })
    except ArticleException as e:
        data.update({
            "authors": [],
            "title": "",
            "text": "",
            "article_text": "",
            "error": str(e)
        })
    return data

async def fetch_and_add_urls():
    while True:
        print("Looping URLS from newspaper3k")
        urls = await get_urls_newspapers()
        for url in urls:
            await add_article_if_not_exists(url)
        await asyncio.sleep(1)  # Wait for 1 seconds before fetching again

async def add_urls_from_file():
    while True:
        print("Looping URLS from file")
        with open(URLS_FILE, "r") as f:
            for line in f:
                await add_article_if_not_exists(line)
        await asyncio.sleep(5)

async def main():
    await asyncio.gather(
        fetch_and_add_urls(),
        add_urls_from_file(),
        parse_articles(),
        is_about_ai(),
        extract_authors(),
        question("question1", QUESTION_1),
        question("question2", QUESTION_2),
        filter_url()
    )

if __name__ == "__main__":
    update_documents_with_new_schema()
    asyncio.run(main())