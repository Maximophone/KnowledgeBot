from newspaper import Article
from dataclasses import dataclass
from typing import List

SOURCES = {
    "lemonde",
    "liberation",
    "lexpress",
    "next.ink",
    "mediapart",

}

@dataclass
class NewsSource:
    name: str
    url: str
    article_xpath: str = "//article//text()"

@dataclass
class Author:
    name: str
    url: str = None

NEWS_SOURCES = [
    NewsSource("lemonde", "http://www.lemonde.fr", "//section//text()"),
    NewsSource("liberation", "https://www.liberation.fr/", "//main//text()"),
    NewsSource("lexpress", "https://www.lexpress.fr/", '(//div[contains(@class, "article")])[0]//text()'),
    NewsSource("next.ink", "https://next.ink/", '//div[@id="article-contenu"]//text()'),
    NewsSource("mediapart", "https://www.mediapart.fr/", "//main//text()"),
    NewsSource("latribune", "https://www.latribune.fr/"),
    NewsSource("lepoint", "https://www.lepoint.fr/"),
    NewsSource("lesechos", "https://www.lesechos.fr/"),
    NewsSource("humanite", "https://www.humanite.fr/"),
    NewsSource("usbeketrica", "https://usbeketrica.com/"),
    NewsSource("ladn", "https://www.ladn.eu/"),
    NewsSource("leparisien", "https://www.leparisien.fr/"),
]

def get_source(url: str) -> NewsSource:
    for source in NEWS_SOURCES:
        if source.name in url: 
            return source
        
def get_article_text(article) -> str:
    source = get_source(article.url)
    if source is None:
        return
    return "\n".join(
        [x.strip() for x in article.doc.xpath(source.article_xpath) 
         if x.strip()])

# def get_article_text(article, source=""):
#     xpath = "//article//text()"
#     if "lemonde" in source:
#         xpath = "//section//text()"
#     if "liberation" in source:
#         xpath = "//main//text()"
#     if "lexpress" in source:
#         xpath = '(//div[contains(@class, "article")])[0]//text()'
#     if "next.ink" in source:
#         xpath = '//div[@id="article-contenu"]//text()'
#     if "mediapart" in source:
#         xpath = "//main//text()"
#     return "\n".join([x.strip() for x in article.doc.xpath(xpath) if x.strip()])

def get_authors_liberation(article: Article) -> List[Author]:
    if article.download_state == 0:
        article.download()
    if not article.is_parsed:
        article.parse()
    authors = []
    head_children = article.doc.head.getchildren()
    i = 0
    while i < len(head_children):
        meta = head_children[i]
        i += 1
        if meta.tag != "meta":
            continue
        if meta.attrib.get("property") != "article:author":
            continue
        author = Author(meta.attrib.get("content").strip())
        next_meta = head_children[i]
        if next_meta.attrib.get("property") == "article:author:url":
            author.url = next_meta.attrib.get("content").strip()
            i += 1
        authors.append(author)
    return authors