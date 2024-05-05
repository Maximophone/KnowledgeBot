from newspaper import Article
from dataclasses import dataclass
from typing import List

@dataclass
class Author:
    name: str
    url: str = None

def get_article_text(article, source=""):
    xpath = "//article//text()"
    if "lemonde" in source:
        xpath = "//section//text()"
    if "liberation" in source:
        xpath = "//main//text()"
    if "lexpress" in source:
        xpath = '(//div[contains(@class, "article")])[0]//text()'
    if "next.ink" in source:
        xpath = '//div[@id="article-contenu"]//text()'
    if "mediapart" in source:
        xpath = "//main//text()"
    return "\n".join([x.strip() for x in article.doc.xpath(xpath) if x.strip()])

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