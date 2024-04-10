import argparse
import ai
from typing import List, Dict
import yaml
import anthropic
import os

beacon_me = """----
[ME]
----"""

beacon_claude = """----
[AI]
----"""

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

# Set your API key
api_key = secrets["claude_api_key"]

# Initialize the Anthropic API client
client = anthropic.Client(api_key=api_key)

#haiku = ai.Claude(client, "haiku")
model = ai.AI("claude-haiku")

def needs_answer(txt):
    return not txt.strip().endswith(beacon_me)

def process_conversation(txt: str) -> List[Dict[str, str]]:
    cut = [t.split(beacon_me) for t in txt.split(beacon_claude)]
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
        model_name = "claude-haiku"

    for fname in os.listdir("conversation"):
        with open(f"conversation/{fname}", "r", encoding="utf-8") as f:
            conv_txt = f.read()

        if not needs_answer(conv_txt):
            print(f"{fname}: No answer needed")
            continue

        print(f"{fname}: Answering...")
        messages = process_conversation(conv_txt)
        #response = haiku.conversation(messages, model_override=model_name, max_tokens = 4096)
        response = model.conversation(messages, model_override=model_name, max_tokens=4096)

        with open(f"conversation/{fname}", "a+", encoding="utf-8") as f:
            f.write("\n" + beacon_claude + "\n" + response + "\n" + beacon_me)

