import argparse
import ai
from typing import List, Dict
import yaml
import anthropic
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import traceback
from beacons import *

DEFAULT_LLM = "sonnet3.5"

# beacon_error = """----
# [ERROR]
# ----"""

# beacon_me = """----
# [ME]
# ----"""

# beacon_claude = """----
# [AI]
# ----"""

def parse_parameters(params_string: str) -> Dict:
    print(params_string)
    parameters = {}
    params = params_string.split(",")
    if len(params) == 1 and ":" not in params[0]:
        # old use case, just the model name, for example =#[opus]
        return {"model": params[0]}
    for param in params:
        param_name, param_value = param.split(":")
        parameters[param_name.strip()] = param_value.strip()
    return parameters

def resolve_reference(reference: str, folder: str, 
    root: str = "G:\\My Drive\\Obsidian") -> List[str]:
    path = f"{root}\\{folder}"
    filenames = reference.split("|")
    contents = []
    for fname in filenames:
        fname = fname.strip()
        if not "." in fname:
            fname = fname + ".md"
        if os.path.isfile(f"{path}\\{fname}"):
            if fname.endswith(".pdf"):
                contents.append(ai.extract_text_from_pdf(f"{path}\\{fname}"))
            else:
                with open(f"{path}\\{fname}", "r", encoding="utf-8") as f:
                    contents.append(f.read())
        else:
            print(f"Error: can't find document {fname}")
            contents.append(f"Error: can't find document {fname}")
    return contents

class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, default_model: str):
        self.default_model = default_model
        self.dont_trigger = set()
        super().__init__()

    def on_modified(self, event):
        debug = False
        print(event.src_path, flush=True)
        print(self.dont_trigger, flush=True)
        if event.is_directory:
            return
        if event.src_path in self.dont_trigger:
            self.dont_trigger.remove(event.src_path)
            return
        try:
            print(f"File {event.src_path} modified", flush=True)
            with open(event.src_path, "r", encoding="utf-8") as f:
                conv_txt = f.read()
            model_name = self.default_model
            system_prompt = None
            reference = None
            folder = None
            if conv_txt.startswith("=#["):
                params_string, conv_txt = conv_txt.split("]",1)
                parameters = parse_parameters(params_string[3:])
                if "model" in parameters:
                    model_name = parameters["model"]
                if "system" in parameters:
                    system_prompt = parameters["system"]
                if "meeting-ref" in parameters:
                    reference = parameters["meeting-ref"]
                    folder = "KnowledgeBot\\Meetings\\Transcriptions"
                if "idea-ref" in parameters:
                    reference = parameters["idea-ref"]
                    folder = "KnowledgeBot\\Ideas\\Transcriptions"
                if "unsorted-ref" in parameters:
                    reference = parameters["unsorted-ref"]
                    folder = "KnowledgeBot\\Unsorted\\Transcriptions"
                if "daily-ref" in parameters:
                    reference = parameters["daily-ref"]
                    folder = "Daily Notes"
                if "doc-ref" in parameters:
                    reference = parameters["doc-ref"]
                    folder = ""
                if "pdf-ref" in parameters:
                    reference = parameters["pdf-ref"]
                    folder = "pdf"
                if "md-ref" in parameters:
                    reference = parameters["md-ref"]
                    folder = "MarkDownload"
                if "debug" in parameters:
                    debug = True
            
            if not needs_answer(conv_txt):
                print("No answer needed", flush=True)
                return
            
            if reference:
                contents = resolve_reference(reference, folder)
                for fname, content in zip(reference.split("|"), contents):
                    conv_txt = f"<document-title>{fname}</document-title>\n<document>{content}</document>\n{conv_txt}"

            if debug:
                print("----------------------------", flush=True)
                print("      DEBUG LOG START", flush=True)
                print("----------------------------", flush=True)
                print("      LLM TEXT", flush=True)
                print("----------------------------", flush=True)
                print(conv_txt.encode('ascii', errors='replace').decode('ascii'))
                print("----------------------------", flush=True)
                print("      DEBUG LOG END", flush=True)
                print("----------------------------", flush=True)

            print(f"Answering with {model_name}...", flush=True)
            messages = process_conversation(conv_txt)

            if system_prompt is not None:
                with open(f"prompts/{system_prompt}.md", "r") as f:
                    system_prompt = f.read()

            #response = haiku.conversation(messages, model_override=model_name, max_tokens = 4096)
            response = model.messages(messages, model_override=model_name, 
                                          max_tokens=4096, system_prompt=system_prompt)

            # We dont want this writing event to trigger another answer
            self.dont_trigger.add(event.src_path)
            with open(event.src_path, "a+", encoding="utf-8") as f:
                f.write("\n" + beacon_ai + "\n" + response + "\n" + beacon_me + "\n")
        except Exception:
            self.dont_trigger.add(event.src_path)
            with open(event.src_path, "a+", encoding="utf-8") as f:
                f.write("\n" + beacon_error + "\n" + traceback.format_exc() + "\n")



with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

# Set your API key
api_key = secrets["claude_api_key"]

# Initialize the Anthropic API client
client = anthropic.Client(api_key=api_key)

#haiku = ai.Claude(client, "haiku")
model = ai.AI("claude-haiku")

def needs_answer(txt):
    return not txt.strip().endswith(beacon_me) and txt

def process_conversation(txt: str) -> List[Dict[str, str]]:
    cut = [t.split(beacon_me) for t in txt.split(beacon_ai)]
    # [[<claude>, <me>], [<claude>, <me>], ... ]
    assert len(cut[0]) == 1 or len(cut[0]) == 2
    assert all(len(x)==2 for x in cut[1:])
    if len(cut[0]) == 1:
        cut[0] = ["", cut[0][0]]
    assert cut[0][0] == ""
    messages = sum([[
        {"role": "assistant", "content": cl.strip()},
        {"role": "user", "content": me.strip()}
    ] for cl, me in cut], [])[1:]
    assert messages[0]["role"] == "user"
    assert messages[-1]["role"] == "user"
    return messages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discord Bot')
    parser.add_argument('--model', help='Model to use')
    args = parser.parse_args()

    if args.model:
        model_name = args.model
    else:
        model_name = DEFAULT_LLM

    path = "conversation"
    event_handler = FileModifiedHandler(model_name)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    print("Ready.", flush=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()