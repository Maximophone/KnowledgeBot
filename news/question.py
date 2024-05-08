"""Asking questions about news articles"""
from ai import AI
from lxml import etree
from dataclasses import dataclass


gemini = AI("gemini1.5")

PROMPT = """Please answer the following question about this article. 

Reply stricly in the following format, with no text outside of these tags. Do not use html.
<reflexions>Your reflexions before answering the question</reflexions>
<answer>Your answer to the question</answer>
<explanations>Your explanations for why you picked this answer to question</explanations>

<question>{question}</question>
<article>{article}</article>
"""

@dataclass
class Answer:
    answer: str = ""
    reflexions: str = ""
    explanations: str = ""
    error: bool = True
    error_message: str = ""
    full_answer: str = ""

def question(article: str, question: str, n_retries=2) -> Answer:
    assert n_retries >= 1, "N retries can't be < 1"
    prompt = PROMPT.format(question = question, article = article)
    response = gemini.message(prompt)
    xml_response_str = "<response>" + response + "</response>"
    answer = Answer()
    answer.full_answer = xml_response_str
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
    

