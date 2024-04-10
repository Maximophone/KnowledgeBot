from ai import Claude
import yaml
import anthropic
import json
from summarisation import get_summary_text
import re

def extract_filenames(text):
    pattern = r'<filename>(.*?)</filename>'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches

def validate_filename(summary, filename):
    return filename in summary

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

# Set your API key
api_key = secrets["claude_api_key"]

# Initialize the Anthropic API client
client = anthropic.Client(api_key=api_key)

with open("prompts/system_prompt_5.md", "r") as f:
    system_prompt_extraction = f.read()

with open("prompts/system_prompt_4.md", "r") as f:
    system_prompt_final = f.read()

with open("summary.json", "r") as f:
    summary = json.load(f)

bot_extraction = Claude(client, "sonnet", system_prompt_extraction)
bot_final = Claude(client, "sonnet", system_prompt_final)

query = "What is, according to you, the best idea contained in my notes?"
#query = "One day, I got shocked by the reaction of a friend of mine when he saw a three legged dog. Tell me this story in details."

message = f"QUERY:{query}\n\n\nNOTES SUMMARY: {get_summary_text(summary)}"

response = bot_extraction.message(message)
print(response)

print("-------------EXTRACTED FILES---------------------")
filenames = extract_filenames(response)

print(filenames)
i=0
while not all([f in summary for f in filenames]) and i<3:
    # some filenames are invalid
    print("-------------------CORRECTION-----------------")
    response = bot_extraction.message("Some of the filenames you provided are invalid. Make sure to refer to the file names and not the title of the notes. Please send your function calls again after correcting for this.")
    print(response)
    print("-------------EXTRACTED FILES---------------------")
    filenames = extract_filenames(response)
    print(filenames)
    i+=1

for filename in filenames:
    with open(f"output/{filename}", "r") as f:
        d = json.load(f)
    summary[filename]["full_text"] = d["text"]

new_message = f"QUERY:{query}\n\n\nNOTES SUMMARY: {get_summary_text(summary)}"

new_response = bot_final.message(message)

print("-------------FINAL RESPONSE---------------------")
print(new_response)


