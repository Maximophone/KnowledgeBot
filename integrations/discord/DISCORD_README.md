# Discord Bot I/O Core Module

A decoupled I/O interface for a Discord bot that handles message inputs and actions, without any business logic.

## Features

- **Clean Separation of Concerns**: I/O layer is completely decoupled from business logic
- **Input Events**: Captures and formats direct messages (DMs) and channel mentions
- **Output Actions**: Provides methods for sending DMs, posting channel messages, and reading message history
- **Strong Typing**: All methods use type hints for better IDE support and code safety
- **Error Handling**: Includes retry mechanisms for rate limits and comprehensive error handling
- **Async Support**: Built with asyncio for optimal performance

## Requirements

- Python 3.8+
- discord.py library
- Required Discord privileged intents:
  - `message_content` (to read message content)
  - `members` (to access member information)

## Installation

1. Add discord.py to your requirements:

```bash
pip install "discord.py>=2.0.0"
```

2. Update your `.env` file with your Discord bot token:

```
DISCORD_BOT_TOKEN=your_bot_token_here
```

## Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select an existing one
3. Go to the "Bot" tab
4. Enable privileged intents:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT
5. Copy the bot token for your `.env` file

## Usage Examples

### Basic Bot Setup

```python
import os
import asyncio
from integrations.discord.core import DiscordIOCore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
discord_token = os.getenv("DISCORD_BOT_TOKEN")

# Initialize the Discord I/O Core
discord_io = DiscordIOCore(token=discord_token)

# Define a callback to handle incoming events
async def handle_event(event):
    print(f"Received event: {event}")
    
    # Echo back DMs
    if event["type"] == "dm":
        user_id = int(event["user_id"])
        await discord_io.send_dm(user_id, f"You said: {event['text']}")
    
    # Reply to mentions
    elif event["type"] == "mention":
        channel_id = int(event["channel_id"])
        await discord_io.post_message(channel_id, f"Hey {event['author_name']}, I noticed your mention!")

# Register the callback
discord_io.set_event_callback(handle_event)

# Run the bot
discord_io.run()
```

### Integration with a "Brain" Module

```python
# brain.py
class Brain:
    def __init__(self, discord_core):
        self.core = discord_core
        self.core.set_event_callback(self.handle_event)
    
    async def handle_event(self, event):
        """Process input events and determine responses."""
        if event["type"] == "dm":
            user_id = int(event["user_id"])
            
            # Get conversation history
            history = await self.core.read_user_dm_history(user_id, limit=10)
            
            # Generate a response (this would be your AI logic)
            response = self.generate_response(event["text"], history)
            
            # Send the response
            await self.core.send_dm(user_id, response)
        
        elif event["type"] == "mention":
            channel_id = int(event["channel_id"])
            
            # Get channel context
            recent_messages = await self.core.read_recent_messages(channel_id, limit=5)
            
            # Generate a response
            response = self.generate_channel_response(event["text"], recent_messages)
            
            # Post the response
            await self.core.post_message(channel_id, response)
    
    def generate_response(self, text, history):
        """Example placeholder for response generation."""
        return f"I received: {text}"
    
    def generate_channel_response(self, text, context):
        """Example placeholder for channel response generation."""
        return f"I was mentioned with: {text}"

# main.py
import os
from dotenv import load_dotenv
from integrations.discord.core import DiscordIOCore
from brain import Brain

# Load environment variables
load_dotenv()
discord_token = os.getenv("DISCORD_BOT_TOKEN")

# Initialize the Discord I/O Core
discord_io = DiscordIOCore(token=discord_token)

# Initialize the brain with the Discord I/O Core
brain = Brain(discord_io)

# Run the bot
discord_io.run()
```

### Using Async Methods Without Blocking

```python
import os
import asyncio
from integrations.discord.core import DiscordIOCore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
discord_token = os.getenv("DISCORD_BOT_TOKEN")

# Initialize the Discord I/O Core
discord_io = DiscordIOCore(token=discord_token)

async def main():
    # Start the bot in the background
    bot_task = asyncio.create_task(discord_io.start_bot())
    
    # Other async operations can continue here
    # For example, sending a startup message to a specific channel
    await discord_io.post_message(channel_id=1234567890, text="Bot started successfully!")
    
    # Or perform periodic tasks
    while True:
        await asyncio.sleep(3600)  # Run every hour
        await discord_io.post_message(channel_id=1234567890, text="Hourly update")

# Run the async main function
asyncio.run(main())
```

## API Reference

### DiscordIOCore

#### Initialization

```python
core = DiscordIOCore(token: str)
```

#### Event Registration

```python
core.set_event_callback(callback: Callable[[Dict[str, Any]], Any])
```

The callback function will receive event dictionaries with the following structure:

**DM Event:**
```
{
    'type': 'dm',
    'user_id': '123456789',
    'text': 'Message content',
    'timestamp': '2023-01-01T12:00:00.000000',
    'author_name': 'User',
    'message_id': '987654321'
}
```

**Mention Event:**
```
{
    'type': 'mention',
    'user_id': '123456789',
    'channel_id': '987654321',
    'guild_id': '555555555',
    'text': 'Message content',
    'timestamp': '2023-01-01T12:00:00.000000',
    'author_name': 'User',
    'message_id': '111111111'
}
```

#### Output Methods

```python
# Send a direct message to a user
await core.send_dm(user_id: int, text: str) -> bool

# Post a message to a channel
await core.post_message(channel_id: int, text: str) -> bool

# Read recent messages from a channel
await core.read_recent_messages(channel_id: int, limit: int = 100) -> List[Dict[str, Any]]

# Read DM history with a specific user
await core.read_user_dm_history(user_id: int, limit: int = 100) -> List[Dict[str, Any]]
```

#### Control Methods

```python
# Start the bot (non-blocking)
await core.start_bot()

# Run the bot (blocking)
core.run()

# Close the bot connection
await core.close()
```

## Performance Considerations

- The module is designed to handle 100+ concurrent servers
- All I/O methods aim for <500ms latency
- Rate limit handling with 3x retries

## Error Handling

- All public methods return success status (`True`/`False`) or empty lists on failure
- Exceptions are caught and logged, never propagated to the caller
- Rate limits are automatically handled with exponential backoff

## Security

- Message content is never logged
- User and channel IDs are validated before performing actions 