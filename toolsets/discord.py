"""Toolset for interacting with Discord."""

import asyncio
import json
from typing import List, Dict, Any
from ai_core.tools import tool
from integrations.discord import DiscordIOCore
from config.secrets import DISCORD_BOT_TOKEN
import threading

# --- Discord Client Initialization ---
# Global instance to hold the DiscordIOCore
discord_io: DiscordIOCore = None
discord_thread: threading.Thread = None
event_loop = None

def initialize_discord_client():
    """Initializes and runs the Discord client in a separate thread."""
    global discord_io, discord_thread, event_loop
    
    if discord_io is not None:
        # Already initialized
        return

    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN is not set in secrets.")
        # Optionally raise an exception or handle this case differently
        raise ValueError("Discord Bot Token is not configured.")

    try:
        # Create a new event loop for the Discord thread
        event_loop = asyncio.new_event_loop()
        
        def run_discord_loop(loop):
            asyncio.set_event_loop(loop)
            global discord_io
            discord_io = DiscordIOCore(token=DISCORD_BOT_TOKEN)
            
            # You might want a simple event handler here for logging or basic checks
            async def on_discord_event(event):
                 print(f"Discord Event Received (in toolset): {event.get('type', 'unknown')}")
                 # Add more handling if needed
            
            discord_io.set_event_callback(on_discord_event)
            
            try:
                loop.run_until_complete(discord_io.start_bot())
            except Exception as e:
                 print(f"Error in Discord run loop: {e}")
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
                print("Discord event loop closed.")

        # Start Discord client in a separate thread
        discord_thread = threading.Thread(target=run_discord_loop, args=(event_loop,), daemon=True)
        discord_thread.start()
        print("Discord client thread started.")
        # Wait briefly for the client to potentially connect (adjust time if needed)
        # This doesn't guarantee readiness but gives it a chance.
        # Proper readiness check would require inter-thread communication (e.g., an Event)
        import time
        time.sleep(5) # Adjust as necessary

    except Exception as e:
        print(f"Failed to initialize Discord client: {e}")
        discord_io = None # Ensure it's None if init fails

# Call initialization when the module is loaded
# Be cautious with top-level initializations like this, especially if the module
# might be imported in contexts where starting the bot isn't desired immediately.
# Consider lazy initialization within the tools if needed.
# initialize_discord_client()

# --- Tool Definitions ---

def run_in_discord_loop(coro):
    """Helper to run async Discord functions from synchronous tool calls."""
    initialize_discord_client()
    if discord_io is None or event_loop is None:
        raise RuntimeError("Discord client is not initialized or event loop is unavailable.")
             
    if not event_loop.is_running():
         raise RuntimeError("Discord event loop is not running.")

    # Ensure the client is ready before proceeding
    # This is a basic check; a more robust solution might use an asyncio.Event
    if not discord_io.client or not discord_io.client.is_ready():
         import time
         print("Discord client not ready, waiting briefly...")
         time.sleep(2) # Wait a bit more
         if not discord_io.client or not discord_io.client.is_ready():
              raise RuntimeError("Discord client is not ready.")

    future = asyncio.run_coroutine_threadsafe(coro, event_loop)
    try:
        # Increased timeout to handle potential delays
        return future.result(timeout=30)
    except asyncio.TimeoutError:
         raise TimeoutError("Discord operation timed out.")
    except Exception as e:
        # Log or handle the exception that occurred within the coroutine
        print(f"Exception in discord coroutine: {e}")
        raise

@tool(
    description="List all accessible text channels in the server(s) the bot is in. Returns a list of channel names and IDs.",
    safe=True
)
def list_discord_channels() -> str:
    """Lists all accessible text channels."""
    initialize_discord_client()
    if not discord_io or not discord_io.client or not discord_io.client.is_ready():
        return json.dumps({"error": "Discord client not ready or not initialized."})
        
    channels = []
    try:
        # Access guilds directly from the client
        for guild in discord_io.client.guilds:
            for channel in guild.text_channels:
                channels.append({"name": channel.name, "id": str(channel.id)})
        return json.dumps(channels)
    except Exception as e:
        return json.dumps({"error": f"Failed to list channels: {str(e)}"})

@tool(
    description="Read the most recent messages from a specific Discord channel.",
    channel_id="The ID of the Discord channel to read messages from.",
    limit="Maximum number of messages to retrieve (default: 50, max: 1000).",
    safe=True
)
def read_discord_messages(channel_id: str, limit: int = 50) -> str:
    """Reads recent messages from a Discord channel."""
    try:
        initialize_discord_client()
        if not discord_io or not discord_io.client or not discord_io.client.is_ready():
            return json.dumps({"error": "Discord client not ready or not initialized."})
        limit = min(max(1, limit), 1000) # Clamp limit between 1 and 1000
        # Use the helper to run the async function
        messages = run_in_discord_loop(
            discord_io.read_recent_messages(int(channel_id), limit=limit)
        )
        return json.dumps(messages)
    except ValueError:
        return json.dumps({"error": "Invalid channel_id format. Must be an integer."})
    except RuntimeError as e:
         return json.dumps({"error": str(e)})
    except TimeoutError as e:
         return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to read messages: {str(e)}"})

@tool(
    description="Send a direct message (DM) to a specific Discord user.",
    user_id="The ID of the Discord user to send the message to.",
    message_text="The content of the message to send.",
    safe=False # Sending messages modifies state
)
def send_discord_dm(user_id: str, message_text: str) -> str:
    """Sends a direct message to a Discord user."""
    try:
        initialize_discord_client()
        if not discord_io or not discord_io.client or not discord_io.client.is_ready():
            return json.dumps({"error": "Discord client not ready or not initialized."})
        # Use the helper to run the async function
        success = run_in_discord_loop(
            discord_io.send_dm(int(user_id), message_text)
        )
        if success:
            return json.dumps({"status": "success", "message": "DM sent successfully."})
        else:
            return json.dumps({"status": "error", "message": "Failed to send DM."})
    except ValueError:
        return json.dumps({"error": "Invalid user_id format. Must be an integer."})
    except RuntimeError as e:
         return json.dumps({"error": str(e)})
    except TimeoutError as e:
         return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to send DM: {str(e)}"})

@tool(
    description="Read the most recent direct messages (DMs) from a specific user.",
    user_id="The ID of the Discord user to read DMs from.",
    limit="Maximum number of messages to retrieve (default: 50, max: 1000).",
    safe=True
)
def read_discord_dm_history(user_id: str, limit: int = 50) -> str:
    """Reads recent DMs from a specific user."""
    try:
        initialize_discord_client()
        if not discord_io or not discord_io.client or not discord_io.client.is_ready():
            return json.dumps({"error": "Discord client not ready or not initialized."})
        limit = min(max(1, limit), 1000) # Clamp limit between 1 and 1000
        # Use the helper to run the async function
        messages = run_in_discord_loop(
            discord_io.read_user_dm_history(int(user_id), limit=limit)
        )
        return json.dumps(messages)
    except ValueError:
        return json.dumps({"error": "Invalid user_id format. Must be an integer."})
    except RuntimeError as e:
         return json.dumps({"error": str(e)})
    except TimeoutError as e:
         return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to read DM history: {str(e)}"})

# Export the tools
TOOLS = [
    list_discord_channels,
    read_discord_messages,
    send_discord_dm,
    read_discord_dm_history,
] 