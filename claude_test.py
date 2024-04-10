import os
import yaml
import anthropic
import ai

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

# Set your API key
api_key = secrets["claude_api_key"]

# Initialize the Anthropic API client
client = anthropic.Client(api_key=api_key)

haiku = ai.Claude(client, "haiku", "Respond only in Yoda-speak.")
# Define the prompt
prompt = "Hello, Claude! How are you doing today?"

response = haiku.message("How are you today?")

# Print Claude's response
print(response)