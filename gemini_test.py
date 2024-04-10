import google.generativeai as genai
import yaml

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

genai.configure(api_key=secrets['gemini_api_key'])

model = genai.GenerativeModel('gemini-1.0-pro-latest')
response = model.generate_content('Please summarise this document: ...')

print(response.text)