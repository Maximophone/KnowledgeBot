import argparse
import ai
from typing import List, Dict, Tuple
import yaml
import anthropic
import os
import traceback
from file_watcher import start_file_watcher
import re
from run_ai import (resolve_reference, parse_parameters, 
    process_conversation)
from file_packager import get_committed_files, format_for_llm, get_markdown_files
from beacons import *

DEFAULT_LLM = "sonnet3.5"
VAULT_PATH = "G:\\My Drive\\Obsidian"
VAULT_EXCLUDE = ["KnowledgeBot\\Meetings", "AI Chats", "MarkDownload"]


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

def insert_file_ref(fname: str = "", folder: str = "", root: str = VAULT_PATH, 
        fpath: str = None, typ: str = "document"):
    fpath = fpath or f"{root}\\{folder}\\{fname.strip()}"
    fname = fname or fpath.rsplit("\\")[-1]
    contents = get_file(fpath)
    return f"<{typ}><filename>{fname}</filename>\n<contents>{contents}</contents></{typ}>"

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

def resolve_refs(text: str, context: Dict[str, str]) -> Tuple[str, List[Tuple[str,str]]]:
    """Here we find references and, we resolve them and replace them
    with the appropriate text.
    A reference has the following format: 
    <ref!value>
    """
    pattern = r'<(\w+)!(?:"([^"]*)"|(.*?))>'
    replacements = {
        "reply": lambda _: "",
        "model": lambda _: "",
        "system": lambda _: "",
        "debug": lambda _: "",
        "temperature": lambda _: "",
        "max_tokens": lambda _: "",
        "mock": lambda _: "",
        "this": lambda _: "<document>"+context["doc_no_ai"]+"</document>\n",
        "repo": pack_repo,
        "vault": lambda _: pack_vault(),
        "meeting": lambda v: insert_file_ref(v, "KnowledgeBot\\Meetings\\Transcriptions"),
        "daily": lambda v: insert_file_ref(v, "Daily Notes"),
        "idea": lambda v: insert_file_ref(v, "KnowledgeBot\\Ideas\\Transcriptions"),
        "unsorted": lambda v: insert_file_ref(v, "KnowledgeBot\\Unsorted\\Transcriptions"),
        "doc": lambda v: insert_file_ref(v, ""),
        "pdf": lambda v: insert_file_ref(v, "pdf"),
        "md": lambda v: insert_file_ref(v, "MarkDownload"),
        "file": lambda v: insert_file_ref(fpath=v),
    }
    found_items = []

    def replacer(match):
        name = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        found_items.append((name, value))
        
        assert name in replacements, f"The parameter {name} is not recognized"
        
        return replacements[name](value)

    result = re.sub(pattern, replacer, text)
    
    return result, found_items

def process_file(file_path, model_name):
    try:
        print(f"File {file_path} modified", flush=True)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        ai_blocks = re.findall(r'<ai!>(.*?)</ai!>', content, re.DOTALL)
        # Replaces the entire block with the response
        replace_blocks = re.findall(r"<ai!rep>(.*?)</ai!rep>", content, re.DOTALL)
        
        doc_no_ai = content
        for block in ai_blocks:
            doc_no_ai = doc_no_ai.replace(f'<ai!>{block}</ai!>', '')
        for block in replace_blocks:
            doc_no_ai = doc_no_ai.replace(f'<ai!rep>{block}</ai!rep>', '')
        
        for block in ai_blocks:
            if '<reply!>' in block:
                # Process the block
                processed_block = process_ai_block(block, model_name, doc_no_ai)
                
                # Replace the old block with the processed one
                content = content.replace(f'<ai!>{block}</ai!>', f'<ai!>{processed_block}</ai!>')
        
        for block in replace_blocks:
            if '<reply!>' in block:
                # Process the block
                processed_block = process_ai_block(block, model_name, doc_no_ai, replace=True)
                
                # Replace the old block with the processed one
                content = content.replace(f'<ai!rep>{block}</ai!rep>', f'{processed_block}')


        # Write the updated content back to the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        os.utime(file_path, None)

    except Exception:
        print(f"Error processing file {file_path}:")
        print(traceback.format_exc())

def process_ai_block(block: str, model_name: str, doc_no_ai: str, replace: bool = False) -> str:
    block = block.replace("<reply!>","")

    try:
        conv_txt = block.strip()
    
        # model_name = DEFAULT_LLM
        # system_prompt = None
        # reference = None
        # folder = None
        # pack_folder = None

        context = {
            "doc_no_ai": doc_no_ai
        }

        conv_txt, params = resolve_refs(conv_txt, context)

        model_name = dict(params).get("model", DEFAULT_LLM)
        system_prompt = dict(params).get("system")
        debug = dict(params).get("debug") == ""
        temperature = float(dict(params).get("temperature", ai.DEFAULT_TEMPERATURE))
        max_tokens = int(dict(params).get("max_tokens", ai.DEFAULT_MAX_TOKENS))
        if "mock" in dict(params):
            model_name = "mock"

        if debug:
            print("---PARAMETERS START---"  , flush=True)
            for name, value in params:
                print(f"{name}: {value}", flush=True)
            print("---PARAMETERS END---", flush=True)
            print("---CONVERTED TEXT START---", flush=True)
            print(conv_txt.encode("utf-8"), flush=True)
            print("---CONVERTED TEXT END---", flush=True)

        print(f"Answering with {model_name}...", flush=True)
        messages = process_conversation(conv_txt)

        if system_prompt is not None:
            with open(f"prompts/{system_prompt}.md", "r") as f:
                system_prompt = f.read()

        response = model.messages(messages, model_override=model_name, 
                                max_tokens=max_tokens, system_prompt=system_prompt, 
                                temperature=temperature, debug=debug)

        # Append the response to the block
        if not replace:
            response = f"{block}{beacon_ai}\n{response}\n{beacon_me}\n"
    except Exception:
        response = f"{block}{beacon_error}\n```sh\n{traceback.format_exc()}```\n"
    return response


def needs_answer(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if not (
        (('<ai!>' in content) and ('</ai!>' in content))
         or 
        (('<ai!rep>' in content) and ('</ai!rep>' in content))):
        return False
    ai_blocks = re.findall(r'<ai!>(.*?)</ai!>', content, re.DOTALL)
    for block in ai_blocks:
        if '<reply!>' in block:
            return True
    ai_rep_blocks = re.findall(r'<ai!rep>(.*?)</ai!rep>', content, re.DOTALL)
    for block in ai_rep_blocks:
        if '<reply!>' in block:
            return True
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian AI Assistant')
    parser.add_argument('--model', help='Model to use')
    args = parser.parse_args()

    model_name = args.model if args.model else DEFAULT_LLM

    def file_callback(file_path):
        process_file(file_path, model_name)

    start_file_watcher(VAULT_PATH, file_callback, needs_answer, use_polling=True)