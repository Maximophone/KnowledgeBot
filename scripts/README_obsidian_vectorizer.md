# Obsidian Vault Vectorizer

This script allows you to vectorize your Obsidian vault and add the notes to a vector database for AI-powered search and retrieval.

## Features

- Interactive CLI menu for ease of use
- Configurable through YAML files
- Directory blacklisting to exclude certain folders
- Progress visualization during processing
- Detailed statistics after completion
- Support for different update modes when processing files

## Requirements

The script requires the following Python packages:
- PyYAML
- inquirer
- rich
- colorama
- openai (for embeddings)

All dependencies should be included in the main project's requirements.txt file.

## Usage

### Interactive Mode

```bash
python scripts/obsidian_vectorizer.py
```

This will launch the interactive CLI menu where you can:
- Vectorize your Obsidian vault
- Edit the configuration
- Display the current configuration
- Exit the program

### Command Line Arguments

```bash
python scripts/obsidian_vectorizer.py --vault-path /path/to/obsidian/vault --config-path config/custom_config.yaml
```

#### Options:

- `--vault-path`: Path to your Obsidian vault (overrides the one in config)
- `--config-path`: Path to a custom configuration file (default: config/obsidian_vectorizer.yaml)
- `--headless`: Run in headless mode without interactive menu (requires a vault path either in config or via --vault-path)

### Batch Mode

For automated processing without user interaction:

```bash
python scripts/obsidian_vectorizer.py --headless
```

This will use the vault path from your configuration file. If you want to override it:

```bash
python scripts/obsidian_vectorizer.py --vault-path /path/to/obsidian/vault --headless
```

## Configuration

The default configuration file is located at `config/obsidian_vectorizer.yaml`. You can edit this file directly or use the interactive configuration editor in the script.

### Configuration Options:

- `vault_path`: Path to your Obsidian vault
- `db_path`: Path to the vector database file
- `recursive`: Whether to search recursively in subfolders
- `max_chunk_size`: Maximum size of each chunk in tokens
- `overlap`: Overlap between chunks in tokens
- `update_mode`: How to handle existing documents
  - `error`: Raise an error if document exists
  - `skip`: Skip if document exists (silent)
  - `update_if_newer`: Update only if timestamp is newer (default)
  - `force`: Always replace existing document
- `model_name`: Name of the embedding model
- `batch_size`: Batch size for embedding API calls
- `blacklist_directories`: List of directories to exclude from vectorization

## Example Configuration

```yaml
vault_path: "/path/to/your/obsidian/vault"
db_path: "data/obsidian_vector_db.sqlite"
recursive: true
max_chunk_size: 2000
overlap: 50
update_mode: "update_if_newer"
model_name: "text-embedding-3-small"
batch_size: 8
blacklist_directories:
  - ".obsidian"
  - ".git"
  - ".trash"
  - "templates"
  - "attachments"
```

## API Key

This script requires an OpenAI API key for generating embeddings. Set the `OPENAI_API_KEY` environment variable before running the script:

```bash
export OPENAI_API_KEY="your-api-key"
```

Or on Windows:

```
set OPENAI_API_KEY=your-api-key
```

## Results

After processing, the script will display:
- Number of files processed
- Number of files skipped
- Number of errors
- Total number of chunks created
- Processing time
- Database statistics 