# KnowledgeBot

KnowledgeBot is a personal AI assistant that leverages Large Language Models (LLMs) to provide a text interface for interacting with LLMs and a system for transcribing and summarizing audio recordings.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/KnowledgeBot.git
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up API keys:
   - Create a `secrets.yml` file in the project root directory.
   - Add the following keys to the file:
     ```yaml
     claude_api_key: "your_claude_api_key"
     gemini_api_key: "your_gemini_api_key"
     openai_api_key: "your_openai_api_key"
     openai_org: "your_openai_organization"
     ```
   - Replace the placeholders with your actual API keys and organization.

## Usage

### Text Interface

To use the text interface for interacting with LLMs, run the following command:
```
python run_ai.py [--model MODEL_NAME]
```

- `--model MODEL_NAME`: (Optional) Specify the model to use. Default is "opus".

The script will monitor the `conversation` directory for changes. When a file is modified, it will process the conversation and generate a response using the specified model.

To use a different model, you can also prefix your text like so:
```
=#[model]
```
The available options are:
- opus
- sonnet
- haiku
- gpt4
- gpt3.5
- gemini1.0
- gemini1.5


### Audio Transcription and Summarization

To transcribe and summarize audio recordings, run the following command:
```
python transcribe.py
```

The script will perform the following tasks:
1. Transcribe audio files from the `Audio` directory and save the transcriptions in the `Transcriptions` directory.
2. Improve the transcriptions and save the improved versions in the `Improved` directory.
3. Summarize the transcriptions and save the summaries in the `Summaries` directory.

The script will continuously monitor the directories and process new files as they are added.

## Project Structure

- `KnowledgeBot-main/`: Project root directory
  - `Audio/`: Directory for storing audio files to be transcribed
  - `Transcriptions/`: Directory for storing transcriptions of audio files
  - `Improved/`: Directory for storing improved versions of transcriptions
  - `Summaries/`: Directory for storing summaries of transcriptions
  - `conversation/`: Directory for storing conversation files for the text interface
  - `prompts/`: Directory for storing prompt templates
  - `ai.py`: Module for interacting with different AI models
  - `bot.py`: Module for the KnowledgeBot functionality
  - `config.py`: Module for configuration management
  - `repeater.py`: Module for running repeated tasks
  - `run_ai.py`: Entry point for the text interface
  - `summarisation.py`: Module for summarizing transcriptions
  - `transcribe.py`: Entry point for audio transcription and summarization


## License

This project is licensed under the [MIT License](LICENSE).
