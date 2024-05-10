"""Asking questions about news articles"""
from ai import AI
from lxml import etree
from dataclasses import dataclass, field
from typing import List
from newspaper import Article


gemini = AI("gemini1.5")

PROMPT = """Please answer the following question about this article. 

Reply stricly in the following format, with no text outside of these tags. Do not use html.
<reflexions>Your reflexions before answering the question</reflexions>
<answer>Your answer to the question</answer>
<explanations>Your explanations for why you picked this answer to question</explanations>

<question>{question}</question>
<article>{article}</article>
"""

MULTI_PROMPT = """You will be provided with a question, inside a <question> tag, and a series of textual contents, inside the tags <text1>, <text2>, etc.
For each textual content, you will provide an answer to the question.

Reply stricly in the following format, with no text outside of these tags.
<reflexions>Your reflexions before you start answering for each text</reflextions>
<answer1>Your answer to the question in relation to text1</answer1>
<answer2>Your answer to the question in relation to text2</answer2>
...
</explanations>Your explanations of the process you used to answer the question for each text</explanations>

<question>{question}</question>
{texts_xml}
"""

SINGLE_TEXT = "<text{i}>{text}</text{i}>"

PROMPT_REFINE_TEXT = """
You will find below a snippet from an HTML page that contains an article. I want you to retrieve and return the plain text of the article.
Please return the text between <article> tags like so:
<article>
The article in plain text
</article>

Snippet:
"""

@dataclass
class Answer:
    answer: str = ""
    reflexions: str = ""
    explanations: str = ""
    error: bool = True
    error_message: str = ""
    full_answer: str = ""
    model: str = ""

@dataclass
class MultiAnswer:
    answers: List[str] = field(default_factory=list)
    reflexions: str = ""
    explanations: str = ""
    error: bool = True
    error_message: str = ""
    full_answer: str = ""
    model: str = ""

@dataclass
class Text:
    answer: str = ""
    error: bool = True
    error_message: str = ""
    full_answer: str = ""
    model: str = ""

def multi_answer_question(texts: List[str], question: str, n_retries=2, model=None):
    assert n_retries >= 1, "N retries can't be < 1"
    model = model or gemini
    texts_xml = "\n".join([SINGLE_TEXT.format(i=i+1, text=text) 
                          for i, text in enumerate(texts)])
    prompt = MULTI_PROMPT.format(question=question, texts_xml=texts_xml)
    response = model.message(prompt, max_tokens = 2000)
    xml_response_str = "<response>" + response + "</response>"
    multi_answer = MultiAnswer()
    multi_answer.full_answer = xml_response_str
    multi_answer.model = model.model_name
    error = None
    while n_retries:
        try:
            xml_response = etree.ElementTree(etree.fromstring(xml_response_str))
            for i in range(len(texts)):
                multi_answer.answers.append(xml_response.find(f"answer{i+1}").text)
            multi_answer.reflexions = xml_response.find("reflexions").text
            multi_answer.explanations = xml_response.find("explanations").text
            multi_answer.error = False
            break
        except (etree.XMLSyntaxError, AttributeError) as e:
            error = e
            n_retries -= 1
    if multi_answer.error:
        multi_answer.error_message = str(error)
    return multi_answer

def answer_question(article: str, question: str, n_retries=2, model=None) -> Answer:
    assert n_retries >= 1, "N retries can't be < 1"
    model = model or gemini
    prompt = PROMPT.format(question = question, article = article)
    response = model.message(prompt)
    xml_response_str = "<response>" + response + "</response>"
    answer = Answer()
    answer.full_answer = xml_response_str
    answer.model = model.model_name
    error = None
    while n_retries:
        try:
            xml_response = etree.ElementTree(etree.fromstring(xml_response_str))
            answer.answer = xml_response.find("answer").text
            answer.reflexions = xml_response.find("reflexions").text
            answer.explanations = xml_response.find("explanations").text
            answer.error = False
            break
        except (etree.XMLSyntaxError, AttributeError) as e:
            error = e
            n_retries -= 1
    if answer.error:
        answer.error_message = str(error)
    return answer

def get_article_text(article_url: str) -> str:
    article = Article(article_url)
    article.download()
    article.parse()
    return article.text

def get_article_text_ai(raw_text: str, n_retries=2, model=None) -> Text:
    assert n_retries >= 1, "N retries can't be < 1"
    model = model or gemini
    prompt = PROMPT_REFINE_TEXT + raw_text
    response = model.message(prompt)
    xml_response_str = "<response>" + response + "</response>"
    text = Text()
    text.full_answer = response
    text.model = model.model_name
    error = None
    while n_retries:
        try:
            xml_response = etree.ElementTree(etree.fromstring(xml_response_str))
            text.answer = xml_response.find("article").text
            text.error = False
            break
        except (etree.XMLSyntaxError, AttributeError) as e:
            error = e
            n_retries -= 1
    if text.error:
        text.error_message = str(error)
    return text

def answer_question_from_url(article_url: str, question: str) -> Answer:
    article_text = get_article_text(article_url)
    return answer_question(article_text, question)

