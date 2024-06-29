import argparse
import ai
from typing import List, Dict, Tuple, Callable
import yaml
import anthropic
import os
import glob
import traceback
from file_watcher import start_file_watcher
import re
from run_ai import process_conversation
from file_packager import get_committed_files, format_for_llm, get_markdown_files
from beacons import *
from parser.tag_parser import parse_tags, process_tags

DEFAULT_LLM = "sonnet3.5"
VAULT_PATH = "G:\\My Drive\\Obsidian"
VAULT_EXCLUDE = ["KnowledgeBot\\Meetings", "AI Chats", "MarkDownload"]

PROMPT_MOD = "You will be passed a document and some instructions to modify this document. Please reply strictly with the text of the new document (no surrounding xml, no narration).\n"

# Load secrets
with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

# Set your API key
api_key = secrets["claude_api_key"]

# Initialize the Anthropic API client
client = anthropic.Client(api_key=api_key)

model = ai.AI("claude-haiku")

def pack_repo(path: str) -> str:
    packaged = get_committed_files(path)
    packaged_txt = format_for_llm(packaged)
    # We need to replace the beacons...
    packaged_txt = packaged_txt.replace(beacon_me, "|ME|").replace(beacon_ai, "|AI|").replace(beacon_error, "|ERROR|")
    return f"<repository>{packaged_txt}</repository>\n"

def pack_vault() -> str:
    packaged = get_markdown_files(VAULT_PATH, VAULT_EXCLUDE)
    packaged_txt = format_for_llm(packaged)
    return f"<vault>{packaged_txt}</vault>\n"

def get_file(fpath) -> str:
    contents = ""
    fname = fpath.rsplit("\\")[-1]
    if not "." in fname:
        # default extension is markdown
        fpath = fpath + ".md"
    if os.path.isfile(fpath):
        if fpath.endswith(".pdf"):
            contents = ai.extract_text_from_pdf(fpath)
        else:
            with open(fpath, "r", encoding="utf-8") as f:
                contents = f.read()
    else:
        print(f"Error: can't find document {fpath}")
        contents = f"Error: can't find document {fpath}"
    return contents

def insert_file_ref(fname: str = "", folder: str = "", root: str = VAULT_PATH, 
        fpath: str = None, typ: str = "document"):
    if fname.startswith("[[") and fname.endswith("]]"):
        # special obsidian format
        fpath = resolve_vault_fname(fname[2:-2])
    else:
        fpath = fpath or f"{root}\\{folder}\\{fname.strip()}"
    fname = fname or fpath.rsplit("\\")[-1]
    contents = get_file(fpath)
    return f"<{typ}><filename>{fname}</filename>\n<contents>{contents}</contents></{typ}>"

remove = lambda *_: ""
REPLACEMENTS_OUTSIDE = {
    "help": lambda *_: "This is the help\n",
    "ai": lambda value, text, context: process_ai_block(text, context, value),
}

REPLACEMENTS_INSIDE = {
    "reply": remove,
    "model": remove,
    "system": remove,
    "debug": remove,
    "temperature": remove,
    "max_tokens": remove,
    "mock": remove,
    "this": lambda v, t, context: f"<document>{context}</document>\n",
    "repo": pack_repo,
    "vault": lambda *_: pack_vault(),
    "meeting": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Meetings\\Transcriptions"),
    "daily": lambda v, t, c: insert_file_ref(v, "Daily Notes"),
    "idea": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Ideas\\Transcriptions"),
    "unsorted": lambda v, t, c: insert_file_ref(v, "KnowledgeBot\\Unsorted\\Transcriptions"),
    "doc": lambda v, t, c: insert_file_ref(v, ""),
    "pdf": lambda v, t, c: insert_file_ref(v, "pdf"),
    "md": lambda v, t, c: insert_file_ref(v, "MarkDownload"),
    "file": lambda v, t, c: insert_file_ref(fpath=v)
}

def get_markdown_files(directory):
    # Use os.path.join for cross-platform compatibility
    search_pattern = os.path.join(directory, '**', '*.md')
    
    # Use glob with recursive=True to search subdirectories
    markdown_files = glob.glob(search_pattern, recursive=True)
    
    return markdown_files

def find_matching_path(file_list, end_path):
    # Normalize the end_path to use OS-specific path separators
    normalized_end = os.path.normpath(end_path)
    
    for full_path in file_list:
        # Normalize the full path as well
        normalized_full = os.path.normpath(full_path)
        
        # Check if the normalized full path ends with the normalized end path
        if normalized_full.endswith(normalized_end):
            return full_path
    
    # If no match is found, return None
    return None

def resolve_vault_fname(fname: str, vault_path: str = VAULT_PATH) -> str:
    """Given a vault filename, returns its path"""
    # I need to get all paths to md files under this directory
    fpaths_set = get_markdown_files(vault_path)
    print(fpaths_set, flush=True)
    fpath = find_matching_path(fpaths_set, fname+".md")
    print(fname, vault_path, flush=True)
    print(fpath, flush=True)
    # could be None, if the filename was not found
    return fpath

def escape_response(response: str) -> str:
    """This removes keywords from the AI's response that would trigger
    the system again, for example "<reply!>"
    """
    for keyword in ["ai", "reply", "help", "this"]:
        response = response.replace(f"<{keyword}!>", f"<{keyword.upper()}!>")
    return response

def process_file(file_path):
    try:
        print(f"File {file_path} modified", flush=True)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        doc_no_ai, _ = process_tags(content, {"ai": lambda *_: ""}) 
        context = {"doc": doc_no_ai, "new_doc": None}
        content, params = process_tags(content, REPLACEMENTS_OUTSIDE, context=context)

        if context["new_doc"]:
            content = context["new_doc"]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        os.utime(file_path, None)

    except Exception:
        print(f"Error processing file {file_path}:")
        print(traceback.format_exc())

def process_ai_block(block: str, context: Dict, option: str) -> str:
    """
    Possible options:
    - None: default
    - "rep": replaces the whole block with the ai's answer
    - "all": replaces the entire document with a new version
    """
    option_txt = option or ""
    _, results = process_tags(block)
    if not "reply" in set([n for n,v,t in results]):
        return f"<ai!{option_txt}>{block}</ai!>"
    # if not "<reply!>" in block:
    #     return f"<ai!{option_txt}>{block}</ai!>"
    block, results = process_tags(block, {"reply": remove})
    try:
        n_replies = [int(v) for n,v,t in results if n=="reply"][0] # THERE CAN ONLY BE ONE!
    except TypeError:
        n_replies = 1
    # block = block.replace("<reply!>","") # has to stay for now because it needs to be replaced in the block,
    # not just what is passed to the LLM

    try:
        conv_txt = block.strip()
    
        conv_txt, results = process_tags(conv_txt, REPLACEMENTS_INSIDE, context=context["doc"])

        params = dict([(n, v) for n, v, t in results])

        model_name = params.get("model", DEFAULT_LLM)
        system_prompt = params.get("system")
        debug = params.get("debug") == ""
        temperature = float(params.get("temperature", ai.DEFAULT_TEMPERATURE))
        max_tokens = int(params.get("max_tokens", ai.DEFAULT_MAX_TOKENS))
        if "mock" in params:
            model_name = "mock"

        if debug:
            print("---PARAMETERS START---"  , flush=True)
            for name, value in params.items():
                print(f"{name}: {value}", flush=True)
            print("---PARAMETERS END---", flush=True)
            print("---CONVERTED TEXT START---", flush=True)
            print(conv_txt.encode("utf-8"), flush=True)
            print("---CONVERTED TEXT END---", flush=True)

        print(f"Answering with {model_name}...", flush=True)
        if not option == "all":
            messages = process_conversation(conv_txt)
        else:
            messages = process_conversation(f"{PROMPT_MOD}<document>{context['doc']}</document><instructions>{conv_txt}</instructions>")

        if system_prompt is not None:
            with open(f"prompts/{system_prompt}.md", "r") as f:
                system_prompt = f.read()

        response = ""
        for i in range(n_replies):
            if n_replies > 1:
                response += f"==[VERSION-{i}]==\n"
            response += model.messages(messages, model_override=model_name, 
                                    max_tokens=max_tokens, system_prompt=system_prompt, 
                                    temperature=temperature, debug=debug)

        # Append the response to the block
        if option is None:
            new_block = f"{block}{beacon_ai}\n{response}\n{beacon_me}\n"
        elif option == "rep":
            return response
        elif option == "all":
            # it does not matter what we return
            context["new_doc"] = response
            return response
    except Exception:
        new_block = f"{block}{beacon_error}\n```sh\n{traceback.format_exc()}```\n"
    return f"<ai!{option_txt}>{new_block}</ai!>"


def needs_answer(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    _, results = process_tags(content)
    all_tags = set([name for name, _, _ in results])
    for rep in REPLACEMENTS_OUTSIDE.keys():
        if rep == "ai":
            # the trigger is more complex with this one
            continue
        if rep in all_tags:
            return True
    if not "ai" in all_tags:
        return False
    ai_results = [r for r in results if r[0] == "ai"]
    for name, value, txt in ai_results:
        _, results = process_tags(txt)
        if "reply" in set(n for n,v,t in results):
        #if '<reply!>' in txt:
            return True
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian AI Assistant')
    args = parser.parse_args()

    def file_callback(file_path):
        process_file(file_path)

    start_file_watcher(VAULT_PATH, file_callback, needs_answer, use_polling=True)