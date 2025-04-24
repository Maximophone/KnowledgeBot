import newspaper
from newspaper import Article, ArticleException
from news.news_utils import get_article_text
import nltk
nltk.download('punkt')
import os
from ai_core import AI
from lxml import etree
from typing import List
import json
from urllib.parse import urlparse, urljoin

haiku = AI("haiku")

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
KEYWORDS_AI = [" ia ", "intelligence artificielle", "machine learning", "reseaux de neurones"]
PARSED_NAME = "parsed.txt"
AUTHORS_FILE = "authors.json"
ERRORS_FILE = "errors.txt"
PROMPT = """Find the names of all the authors in the following article. There can be one or several authors. They should all be listed at the same place in the text, either towards the begining or towards the end. Return the result in the following form:
<authors>
    <author>First Author</author>
    ...
</authors>

"""
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0'
NEWSPAPER_CONFIG = newspaper.Config()
NEWSPAPER_CONFIG.browser_user_agent = USER_AGENT

def create_if_not_exist(fpath: str, default=""):
    if not os.path.isfile(fpath):
        with open(fpath, "w") as f:
            f.write(default)

def clean(source_name: str):
    return source_name.split("://")[1].replace("/","")

class AuthorsException(Exception):
    def __init__(self, error_msg: str):
        self.error_msg = error_msg
        super().__init__()

def get_authors(article: Article, source: str) -> List[str]:
    article.download()
    article.parse()
    article_text = get_article_text(article, source)
    if not article_text:
        raise AuthorsException("Could not find article text")
    response = haiku.message(PROMPT + article_text).content
    try:
        tree = etree.ElementTree(etree.fromstring("<response>" + response + "</response>"))
    except etree.XMLSyntaxError:
        raise AuthorsException(f"LLM returned invalid XML: {response}")
    if not tree.find("authors"):
        raise AuthorsException(
            f"LLM did not return an <authors> tag. LLM's response: {response}"
            )
    authors = [x.text for x in tree.find("authors").findall("author")]
    return authors

def extract_authors(output_dir: str):
    create_if_not_exist(f"{output_dir}/{AUTHORS_FILE}")
    urls_to_authors = []
    with open(f"{output_dir}/{AUTHORS_FILE}", "r") as f:
        for line in f:
            if line == "":
                continue
            urls_to_authors.append(json.loads(line))
    done_urls = [data["url"] for data in urls_to_authors]
    for source in NEWSPAPERS:
        clean_name = clean(source)
        fname = f"{output_dir}/{clean_name}.txt"
        create_if_not_exist(fname)
        with open(fname, "r") as f:
            urls_txt = f.read()
        urls = urls_txt.split("\n")
        for url in urls:
            try:
                if url in done_urls:
                    # we have already extracted this one
                    continue
                print(url, flush=True)
                article = Article(url, config=NEWSPAPER_CONFIG)
                article.download()
                article.parse()
                error = None
                try:
                    authors = get_authors(article, source)
                except AuthorsException as e:
                    authors = []
                    error = e.error_msg
                data = {"url": url, "authors": authors, "source": source, "error": error}
                with open(f"{output_dir}/{AUTHORS_FILE}", "a+", encoding="utf-8") as f:
                    f.write(json.dumps(data) + "\n")
            except ArticleException as e:
                print(e)
                if "429" in str(e):
                    print("STOPPING WITH THIS SOURCE")
                    break
                elif "404" in str(e):
                    data = {"url": url, "authors": None, "source": source, "error": str(e)}
                    with open(f"{output_dir}/{AUTHORS_FILE}", "a+", encoding="utf-8") as f:
                        f.write(json.dumps(data) + "\n")
                else:
                    continue

def clean_url(url: str) -> str:
    return urljoin(url, urlparse(url))

def get_urls_newspapers() -> List[str]:
    """Sources article links from the newspaper library"""
    articles_urls = []
    for source in NEWSPAPERS:
        paper = newspaper.build(source, memoize_articles=False, config=NEWSPAPER_CONFIG)
        articles_urls.extend([
            clean_url(article.url) for article in paper.articles])
    return articles_urls

def get_all_ai_articles(output_dir: str):
    create_if_not_exist(f"{output_dir}/{ERRORS_FILE}")
    with open(f"{output_dir}/{PARSED_NAME}", "r") as f:
        parsed_txt = f.read()
    parsed = parsed_txt.split("\n")
    # this tells us which ones we have already done, we can skip them

    for source in NEWSPAPERS:
        print(f"SOURCE: {source}", flush=True)
        clean_name = clean(source)
        paper = newspaper.build(source, language="fr", memoize_articles=False, config=NEWSPAPER_CONFIG)
        print(paper.size(), flush=True)
        fname = f"{output_dir}/{clean_name}.txt"
        if not os.path.isfile(fname):
            with open(fname, "w") as f:
                f.write("")
        for article in paper.articles:
            try:
                if article.url in parsed:
                    # already done
                    continue
                print(article.url, flush=True)
                article.download()
                article.parse()
                
                if any(keyword in article.text.lower() for keyword in KEYWORDS_AI):
                    # We save this url to a file corresponding to this paper
                    with open(fname, "a+") as f:
                        f.write(article.url + "\n")
                
                with open(f"{output_dir}/{PARSED_NAME}", "a+") as f:
                        f.write(article.url + "\n")

            except ArticleException as e:
                print(e)
                if "429" in str(e):
                    print("STOPPING WITH THIS SOURCE")
                    break
                elif "404" in str(e):
                    with open(f"{output_dir}/{ERRORS_FILE}", "a+", encoding="utf-8") as f:
                        f.write(article.url + "\n")
                    with open(f"{output_dir}/{PARSED_NAME}", "a+") as f:
                        f.write(article.url + "\n")
                else:
                    continue



