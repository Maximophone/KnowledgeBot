from typing import List, Dict
import sys
from datetime import datetime as dt
from .types import Message
from .image_utils import get_image_dimensions_from_base64

TOKEN_COUNT_FILE = "token_count.csv"

def n_tokens(text: str) -> int:
    return len(text) // 4

def n_tokens_images(images: List[Dict]) -> int:
    total = 0
    for image in images:
        width, height = get_image_dimensions_from_base64(image["data"])
        total += width*height // 750 # (anthropic's estimation of # of tokens)
    return total

def count_tokens_input(messages: List[Message], system_prompt: str) -> int:
    text = system_prompt
    images = []
    for m in messages:
        for content in m.content:
            if content.type == "text":
                text += content.text
            elif content.type == "image":
                images.append(content.image)
    return n_tokens(text) + n_tokens_images(images)

def count_tokens_output(response: str):
    return n_tokens(response)

def log_token_use(model: str, n_tokens: int, input: bool = True, 
                  fpath: str=TOKEN_COUNT_FILE):
    t = str(dt.now())
    script = sys.argv[0]
    with open(fpath, "a+") as f:
        if input:
            f.write(f"{model},input,{n_tokens},{t},{script}\n")
        else:
            f.write(f"{model},output,{n_tokens},{t},{script}\n") 