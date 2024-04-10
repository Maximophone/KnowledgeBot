from openai import OpenAI, BadRequestError
import json
import jsonschema
import yaml
import os

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

openai_organization = "org-DP5OE4ilCc68WugMCjHvlNCN"

client = OpenAI(api_key = secrets["openai_api_key"], organization=openai_organization)

prompt = """
You are a skilled personal assistant. You will be provided with a transcribed audio note. It could come from the recording of a meeting, someone voicing an idea out loud, conversations...
You will generate:
- A title for the note, in a single sentence
- A summary, that can be at most 200 words long
- A list of tags or keywords, identifying key concepts, topics, and themes that can be used to categorize the note accurately. 

The notes can be provided in English or French, but all your output must be in English.

Please provide your response in json format as follows:
{
"title": "...",
"summary": "...",
"tags": ["...", "...", ...]
}

This is important: your response should only contain the JSON object, nothing else.

Here is the note:

"""

expected_schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}} 
    },
    "required": ["title", "summary", "tags"] 
}

def summarise(note: str):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", # Or another suitable model
        messages=[{
            "role": "system",
            "content": prompt + note
        }]
    )
    extracted_data_json = response.choices[0].message.content.strip()
    try:
        extracted_data = json.loads(extracted_data_json)  # Load as JSON
        jsonschema.validate(instance=extracted_data, schema=expected_schema)
        return extracted_data  # Return a Python dictionary
    except (json.JSONDecodeError, jsonschema.ValidationError) as e:
        print(f"Error decoding JSON: {e}")
        return {"error": str(e)}

def summarise_all(input_dir, output, excluded):
    final_dict = {}
    for fname in os.listdir(input_dir):
        if fname in excluded:
            continue
        print(fname, flush=True)
        with open(f"{input_dir}/{fname}", "r") as f:
            d = json.load(f)
        note = d["text"]
        try:
            summary = summarise(note)
        except BadRequestError as e:
            print(e)
            summary = {"error": str(e)}
        final_dict[fname] = summary
    with open(output, "w") as f:
        json.dump(final_dict, f)
    return final_dict

def get_summary_text(summary_dict) -> str:
    text = ""
    for fname, entry in summary_dict.items():
        if "error" in entry:
            continue
        entry_text = (f"Title: {entry['title']}\n" +
            f"Tags: {','.join(entry['tags'])}\n" +
            f"File Name: {fname}\n" +
            f"Summary: {entry['summary']}\n")
        if "full_text" in entry:
            entry_text += f"Full Text: {entry['full_text']}\n"
        text += entry_text + "\n"
    return text

REBUILD=False
if __name__ == "__main__":
    excluded = [
        "Continent – Sunday at 02_01.m4a.json"
    ]
    if REBUILD:
        final_dict = summarise_all("output", "summary.json", excluded)
    else:
        with open("summary.json", "r") as f:
            final_dict = json.load(f)
    
    summary_text = get_summary_text(final_dict)
    with open("summary.txt", "w", encoding="utf-8") as f:
        f.write(summary_text)