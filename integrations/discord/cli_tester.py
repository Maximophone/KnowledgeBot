#!/usr/bin/env python3
"""
Discord Bot CLI Testing Interface

This tool provides a command-line interface to monitor and control the Discord bot
for testing purposes. It displays all incoming events and allows manual triggering
of output methods.
"""

import os
import sys
import asyncio
import argparse
import json
import time
from datetime import datetime
import threading
import cmd
import shlex
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from integrations.discord.core import DiscordIOCore

# Store received events for display and inspection
events_log = []
# Lock for thread-safe operations on the events log
events_lock = threading.Lock()
# Global event loop
event_loop = None
# Ready flag for Discord connection
bot_ready = threading.Event()

class DiscordCliTester(cmd.Cmd):
    """Interactive CLI for testing the Discord bot I/O core."""
    
    intro = """
    =================================================================
    Discord Bot CLI Testing Interface
    =================================================================
    Type 'help' or '?' to list commands.
    This interface allows you to monitor incoming events and manually
    trigger output methods to test the Discord I/O Core functionality.
    
    Waiting for Discord bot to connect...
    """
    prompt = "discord-bot> "
    
    def __init__(self, discord_io: DiscordIOCore, loop: asyncio.AbstractEventLoop):
        """Initialize the CLI tester with a reference to the Discord I/O core."""
        super().__init__()
        self.discord_io = discord_io
        self.running = True
        self.event_display_enabled = True
        self.auto_echo = False
        self.readline_available = False
        self.loop = loop
        self.ready_checked = False
        
        # Check if readline is available (might not be on Windows)
        try:
            import readline
            self.readline_available = True
        except ImportError:
            # readline not available, we'll use simpler display
            pass
        
        # Start event display thread
        self.display_thread = threading.Thread(target=self._event_display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Start waiting for bot to be ready
        self.wait_thread = threading.Thread(target=self._wait_for_ready)
        self.wait_thread.daemon = True
        self.wait_thread.start()
    
    def _wait_for_ready(self):
        """Wait for the bot to be ready and update the prompt."""
        # Wait a bit for the bot to connect
        time.sleep(5)
        
        # Check if the client is connected by trying to access its properties
        try:
            # This will be set once the bot is properly connected
            user = self.discord_io.client.user
            if user:
                print(f"\nBot connected and ready! Logged in as {user.name}.")
                bot_ready.set()
                self.prompt = f"discord-bot ({user.name})> "
                return
        except Exception as e:
            print(f"\nFailed to get bot status: {str(e)}")
        
        # If we get here, the bot didn't connect within the expected time
        print("\nWarning: Bot connection verification timed out. Some commands may not work.")
        self.prompt = "discord-bot (unknown)> "
    
    def _event_display_loop(self):
        """Background thread to display incoming events."""
        last_displayed_index = -1
        
        while self.running:
            if self.event_display_enabled:
                with events_lock:
                    # Display any new events
                    if len(events_log) > last_displayed_index + 1:
                        for i in range(last_displayed_index + 1, len(events_log)):
                            event = events_log[i]
                            event_time = datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S')
                            
                            # Print the event
                            if self.readline_available:
                                # Try to clear the current command line and restore it after printing
                                try:
                                    import readline
                                    sys.stdout.write('\r' + ' ' * (len(self.prompt) + len(readline.get_line_buffer())) + '\r')
                                    
                                    if event['type'] == 'dm':
                                        print(f"\n[{event_time}] DM from {event['author_name']} ({event['user_id']}): {event['text']}")
                                    elif event['type'] == 'mention':
                                        print(f"\n[{event_time}] Mention in #{event.get('channel_name', 'unknown')} ({event['channel_id']}) by {event['author_name']}: {event['text']}")
                                    
                                    sys.stdout.write(self.prompt + readline.get_line_buffer())
                                    sys.stdout.flush()
                                except:
                                    # Fallback on error
                                    if event['type'] == 'dm':
                                        print(f"\n[{event_time}] DM from {event['author_name']} ({event['user_id']}): {event['text']}")
                                    elif event['type'] == 'mention':
                                        print(f"\n[{event_time}] Mention in #{event.get('channel_name', 'unknown')} ({event['channel_id']}) by {event['author_name']}: {event['text']}")
                            else:
                                # Simple print without readline
                                if event['type'] == 'dm':
                                    print(f"\n[{event_time}] DM from {event['author_name']} ({event['user_id']}): {event['text']}")
                                elif event['type'] == 'mention':
                                    print(f"\n[{event_time}] Mention in #{event.get('channel_name', 'unknown')} ({event['channel_id']}) by {event['author_name']}: {event['text']}")
                            
                        last_displayed_index = len(events_log) - 1
            
            # Check if bot is ready after a bit of time
            if not self.ready_checked and not bot_ready.is_set() and time.time() > 10:
                self.ready_checked = True
                # Try to detect if the bot is actually connected despite not getting a ready event
                try:
                    if hasattr(self.discord_io, 'client') and self.discord_io.client.user is not None:
                        user_name = self.discord_io.client.user.name
                        print(f"\nBot seems to be connected as {user_name}. Setting ready state.")
                        bot_ready.set()
                        self.prompt = f"discord-bot ({user_name})> "
                except Exception:
                    pass
                
            time.sleep(0.1)  # Short sleep to avoid CPU thrashing
    
    async def handle_event(self, event: Dict[str, Any]):
        """Event handler for Discord events."""
        # Check if it's a ready event
        if event.get('type') == 'ready':
            print("\nDiscord bot is now connected!")
            bot_ready.set()
            return
            
        # Add timestamp for display
        event['timestamp'] = datetime.now().timestamp()
        
        # Add to events log
        with events_lock:
            events_log.append(event)
            event_index = len(events_log) - 1
        
        # Auto-echo if enabled
        if self.auto_echo:
            if event['type'] == 'dm':
                user_id = int(event['user_id'])
                await self.discord_io.send_dm(user_id, f"[AUTO-ECHO] You said: {event['text']}")
                print(f"Auto-echoed to user {user_id}")
            elif event['type'] == 'mention':
                channel_id = int(event['channel_id'])
                await self.discord_io.post_message(channel_id, f"[AUTO-ECHO] @{event['author_name']} mentioned me with: {event['text']}")
                print(f"Auto-echoed to channel {channel_id}")
    
    def run_coroutine(self, coro):
        """Helper method to run coroutines in the event loop."""
        # We need to handle the case where the bot just connected but we haven't detected it yet
        if not bot_ready.is_set() and hasattr(self.discord_io, 'client') and self.discord_io.client.user is not None:
            bot_ready.set()
            user_name = self.discord_io.client.user.name
            self.prompt = f"discord-bot ({user_name})> "
            print(f"\nBot is connected as {user_name}.")
        elif not bot_ready.is_set():
            print("Warning: Bot may not be fully connected yet. Command may not work.")
        
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return future.result(timeout=60)  # 60 second timeout - increase from 30
        except asyncio.TimeoutError:
            print("Error: Operation timed out. This might be because:")
            print("  - The Discord bot is not fully connected")
            print("  - The Discord API is experiencing issues")
            print("  - The requested operation is taking too long")
            print("Try again in a few moments.")
            return None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None
    
    def do_status(self, arg):
        """
        Check the connection status of the Discord bot.
        Usage: status
        """
        if bot_ready.is_set():
            user_name = "Unknown"
            try:
                if hasattr(self.discord_io, 'client') and self.discord_io.client.user is not None:
                    user_name = self.discord_io.client.user.name
            except:
                pass
            print(f"Discord bot is connected and ready as {user_name}.")
        else:
            print("Discord bot is not connected yet.")
            
        print(f"Events received: {len(events_log)}")
        
        # Try to get additional information about the bot's state
        try:
            if hasattr(self.discord_io, 'client'):
                if self.discord_io.client.is_closed():
                    print("Warning: Discord client connection is closed.")
                else:
                    print("Discord client connection is open.")
                    
                if self.discord_io.client.is_ready():
                    print("Discord client is marked as ready.")
                else:
                    print("Discord client is not marked as ready.")
                    
                print(f"Latency: {self.discord_io.client.latency:.2f}s")
        except Exception as e:
            print(f"Could not get detailed status: {str(e)}")
    
    def do_dm(self, arg):
        """
        Send a direct message to a user.
        Usage: dm <user_id> <message>
        """
        args = shlex.split(arg)
        if len(args) < 2:
            print("Error: Missing arguments. Usage: dm <user_id> <message>")
            return
        
        user_id = args[0]
        message = ' '.join(args[1:])
        
        try:
            user_id_int = int(user_id)
            # Get direct executor access to the bot's event loop
            if hasattr(self.discord_io.client, 'loop') and self.discord_io.client.loop.is_running():
                result = asyncio.run_coroutine_threadsafe(
                    self.discord_io.send_dm(user_id_int, message),
                    self.discord_io.client.loop  # Use the bot's own event loop
                ).result(timeout=30)
                if result:
                    print(f"DM sent to user {user_id}: {message}")
                else:
                    print(f"Failed to send DM to user {user_id}")
            else:
                # Fallback to our loop
                self.run_coroutine(self.discord_io.send_dm(user_id_int, message))
                print(f"DM sent to user {user_id}: {message}")
        except ValueError:
            print(f"Error: User ID must be a number, got '{user_id}'")
        except asyncio.TimeoutError:
            print("Error: Operation timed out. The Discord API might be experiencing issues.")
        except Exception as e:
            print(f"Error sending DM: {str(e)}")
    
    def do_post(self, arg):
        """
        Post a message to a channel.
        Usage: post <channel_id> <message>
        """
        args = shlex.split(arg)
        if len(args) < 2:
            print("Error: Missing arguments. Usage: post <channel_id> <message>")
            return
        
        channel_id = args[0]
        message = ' '.join(args[1:])
        
        try:
            channel_id_int = int(channel_id)
            # Get direct executor access to the bot's event loop
            if hasattr(self.discord_io.client, 'loop') and self.discord_io.client.loop.is_running():
                result = asyncio.run_coroutine_threadsafe(
                    self.discord_io.post_message(channel_id_int, message),
                    self.discord_io.client.loop  # Use the bot's own event loop
                ).result(timeout=30)
                if result:
                    print(f"Message posted to channel {channel_id}: {message}")
                else:
                    print(f"Failed to post message to channel {channel_id}")
            else:
                # Fallback to our loop
                self.run_coroutine(self.discord_io.post_message(channel_id_int, message))
                print(f"Message posted to channel {channel_id}: {message}")
        except ValueError:
            print(f"Error: Channel ID must be a number, got '{channel_id}'")
        except asyncio.TimeoutError:
            print("Error: Operation timed out. The Discord API might be experiencing issues.")
        except Exception as e:
            print(f"Error posting message: {str(e)}")
    
    def do_history(self, arg):
        """
        Get message history from a channel.
        Usage: history channel <channel_id> [limit]
           or: history dm <user_id> [limit]
        """
        args = shlex.split(arg)
        if len(args) < 2:
            print("Error: Missing arguments. Usage: history <channel|dm> <id> [limit]")
            return
        
        history_type = args[0].lower()
        target_id = args[1]
        limit = 10  # Default limit
        
        if len(args) > 2:
            try:
                limit = int(args[2])
            except ValueError:
                print(f"Warning: Invalid limit '{args[2]}', using default of 10")
        
        try:
            target_id_int = int(target_id)
            
            # Get direct executor access to the bot's event loop
            if hasattr(self.discord_io.client, 'loop') and self.discord_io.client.loop.is_running():
                if history_type == "channel":
                    messages = asyncio.run_coroutine_threadsafe(
                        self.discord_io.read_recent_messages(target_id_int, limit),
                        self.discord_io.client.loop
                    ).result(timeout=30)
                    source = f"channel {target_id}"
                elif history_type == "dm":
                    messages = asyncio.run_coroutine_threadsafe(
                        self.discord_io.read_user_dm_history(target_id_int, limit),
                        self.discord_io.client.loop
                    ).result(timeout=30)
                    source = f"DM with user {target_id}"
                else:
                    print(f"Error: Unknown history type '{history_type}'. Use 'channel' or 'dm'")
                    return
            else:
                # Fallback to our loop
                if history_type == "channel":
                    messages = self.run_coroutine(self.discord_io.read_recent_messages(target_id_int, limit))
                    source = f"channel {target_id}"
                elif history_type == "dm":
                    messages = self.run_coroutine(self.discord_io.read_user_dm_history(target_id_int, limit))
                    source = f"DM with user {target_id}"
                else:
                    print(f"Error: Unknown history type '{history_type}'. Use 'channel' or 'dm'")
                    return
            
            if not messages:
                print(f"No messages found in {source}")
                return
            
            print(f"\n=== Last {len(messages)} messages from {source} ===")
            for i, msg in enumerate(messages):
                time_str = datetime.fromisoformat(msg['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{time_str}] {msg['author_name']} ({msg['author_id']}): {msg['content']}")
            
        except ValueError:
            print(f"Error: ID must be a number, got '{target_id}'")
        except asyncio.TimeoutError:
            print("Error: Operation timed out. The Discord API might be experiencing issues.")
        except Exception as e:
            print(f"Error retrieving history: {str(e)}")
    
    def do_events(self, arg):
        """
        Display all received events or control event display.
        Usage: events show [count]  - Show the last N events
               events on           - Enable real-time event display
               events off          - Disable real-time event display
        """
        args = shlex.split(arg)
        if not args:
            print("Error: Missing arguments. Usage: events <show|on|off> [count]")
            return
        
        command = args[0].lower()
        
        if command == "show":
            count = 10  # Default
            if len(args) > 1:
                try:
                    count = int(args[1])
                except ValueError:
                    print(f"Warning: Invalid count '{args[1]}', using default of 10")
            
            with events_lock:
                if not events_log:
                    print("No events recorded yet")
                    return
                
                start_index = max(0, len(events_log) - count)
                print(f"\n=== Last {min(count, len(events_log))} events ===")
                for i in range(start_index, len(events_log)):
                    event = events_log[i]
                    event_time = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    if event['type'] == 'dm':
                        print(f"[{i}] [{event_time}] DM from {event['author_name']} ({event['user_id']}): {event['text']}")
                    elif event['type'] == 'mention':
                        print(f"[{i}] [{event_time}] Mention in channel {event['channel_id']} by {event['author_name']}: {event['text']}")
        
        elif command == "on":
            self.event_display_enabled = True
            print("Real-time event display enabled")
        
        elif command == "off":
            self.event_display_enabled = False
            print("Real-time event display disabled")
        
        else:
            print(f"Error: Unknown command '{command}'. Use 'show', 'on', or 'off'")
    
    def do_export(self, arg):
        """
        Export all received events to a JSON file.
        Usage: export <filename>
        """
        args = shlex.split(arg)
        if not args:
            print("Error: Missing filename. Usage: export <filename>")
            return
        
        filename = args[0]
        
        try:
            with events_lock:
                with open(filename, 'w') as f:
                    json.dump(events_log, f, indent=2)
            print(f"Exported {len(events_log)} events to {filename}")
        except Exception as e:
            print(f"Error exporting events: {str(e)}")
    
    def do_reply(self, arg):
        """
        Reply to a specific event by its index.
        Usage: reply <event_index> <message>
        """
        args = shlex.split(arg)
        if len(args) < 2:
            print("Error: Missing arguments. Usage: reply <event_index> <message>")
            return
        
        try:
            event_index = int(args[0])
            message = ' '.join(args[1:])
            
            with events_lock:
                if event_index < 0 or event_index >= len(events_log):
                    print(f"Error: Event index {event_index} out of range (0-{len(events_log)-1})")
                    return
                
                event = events_log[event_index]
            
            # Get direct executor access to the bot's event loop
            if hasattr(self.discord_io.client, 'loop') and self.discord_io.client.loop.is_running():
                if event['type'] == 'dm':
                    user_id = int(event['user_id'])
                    result = asyncio.run_coroutine_threadsafe(
                        self.discord_io.send_dm(user_id, message),
                        self.discord_io.client.loop
                    ).result(timeout=30)
                    if result:
                        print(f"Reply sent to user {user_id}: {message}")
                    else:
                        print(f"Failed to send reply to user {user_id}")
                elif event['type'] == 'mention':
                    channel_id = int(event['channel_id'])
                    result = asyncio.run_coroutine_threadsafe(
                        self.discord_io.post_message(channel_id, message),
                        self.discord_io.client.loop
                    ).result(timeout=30)
                    if result:
                        print(f"Reply posted to channel {channel_id}: {message}")
                    else:
                        print(f"Failed to post reply to channel {channel_id}")
            else:
                # Fallback to our loop
                if event['type'] == 'dm':
                    user_id = int(event['user_id'])
                    self.run_coroutine(self.discord_io.send_dm(user_id, message))
                    print(f"Reply sent to user {user_id}: {message}")
                elif event['type'] == 'mention':
                    channel_id = int(event['channel_id'])
                    self.run_coroutine(self.discord_io.post_message(channel_id, message))
                    print(f"Reply posted to channel {channel_id}: {message}")
            
        except ValueError:
            print(f"Error: Event index must be a number, got '{args[0]}'")
        except asyncio.TimeoutError:
            print("Error: Operation timed out. The Discord API might be experiencing issues.")
        except Exception as e:
            print(f"Error sending reply: {str(e)}")
    
    def do_list(self, arg):
        """
        List information about servers, channels, or users.
        Currently a placeholder since these require additional API endpoints.
        """
        print("This feature requires additional Discord API endpoints.")
        print("It will be implemented in a future version.")
    
    def do_echo(self, arg):
        """
        Enable or disable automatic echoing of messages.
        Usage: echo <on|off>
        """
        args = shlex.split(arg)
        if not args:
            print("Error: Missing mode. Usage: echo <on|off>")
            return
        
        mode = args[0].lower()
        
        if mode == "on":
            self.auto_echo = True
            print("Auto-echo enabled. The bot will automatically reply to all messages.")
        elif mode == "off":
            self.auto_echo = False
            print("Auto-echo disabled. The bot will not automatically reply to messages.")
        else:
            print(f"Error: Unknown mode '{mode}'. Use 'on' or 'off'")
    
    def do_reconnect(self, arg):
        """
        Attempt to reconnect the Discord bot if it's disconnected.
        Usage: reconnect
        """
        print("Attempting to reconnect Discord bot...")
        bot_ready.clear()
        
        try:
            # Restart the Discord client using its own loop
            if hasattr(self.discord_io.client, 'loop') and self.discord_io.client.loop.is_running():
                result = asyncio.run_coroutine_threadsafe(
                    self.discord_io.reconnect(),
                    self.discord_io.client.loop
                ).result(timeout=30)
                if result:
                    print("Reconnection successful! Waiting for bot to be fully ready...")
                else:
                    print("Reconnection attempt failed.")
            else:
                # Fallback to our loop
                result = self.run_coroutine(self.discord_io.reconnect())
                if result:
                    print("Reconnection successful! Waiting for bot to be fully ready...")
                else:
                    print("Reconnection attempt failed.")
            
            # Wait for reconnection
            if bot_ready.wait(timeout=30):
                user_name = self.discord_io.client.user.name if hasattr(self.discord_io.client, 'user') and self.discord_io.client.user else "Unknown"
                print(f"Bot successfully reconnected as {user_name}!")
                self.prompt = f"discord-bot ({user_name})> "
            else:
                print("Reconnection timed out. Bot may still be disconnected.")
                self.prompt = "discord-bot (disconnected)> "
                
        except Exception as e:
            print(f"Error during reconnection: {str(e)}")
            self.prompt = "discord-bot (disconnected)> "
    
    def do_help(self, arg):
        """List available commands with their descriptions."""
        if arg:
            # Show help for a specific command
            super().do_help(arg)
        else:
            print("\nAvailable commands:")
            print("  dm <user_id> <message>          - Send a direct message to a user")
            print("  post <channel_id> <message>     - Post a message to a channel")
            print("  reply <event_index> <message>   - Reply to a specific event")
            print("  history dm <user_id> [limit]    - Show DM history with a user")
            print("  history channel <channel_id> [limit] - Show channel message history")
            print("  events show [count]             - Show last N events")
            print("  events on|off                   - Enable/disable real-time event display")
            print("  echo on|off                     - Enable/disable auto-echo of messages")
            print("  export <filename>               - Export events to JSON file")
            print("  status                          - Check bot connection status")
            print("  reconnect                       - Attempt to reconnect the bot")
            print("  list                            - List servers/channels/users (placeholder)")
            print("  help [command]                  - Show help for all commands or a specific command")
            print("  quit, exit                      - Exit the CLI tester")
    
    def do_quit(self, arg):
        """Exit the CLI tester."""
        print("Shutting down CLI tester...")
        self.running = False
        return True
    
    def do_exit(self, arg):
        """Exit the CLI tester."""
        return self.do_quit(arg)

def main():
    """Main entry point for the CLI tester."""
    parser = argparse.ArgumentParser(description="Discord Bot CLI Testing Interface")
    parser.add_argument("--token", help="Discord bot token (overrides environment variable)")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get Discord token
    token = args.token or os.getenv("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        try:
            # Try to import from config if exists
            from config.secrets import DISCORD_BOT_TOKEN
            token = DISCORD_BOT_TOKEN
        except ImportError:
            pass
    
    if not token:
        print("Error: Discord bot token not provided.")
        print("Either set the DISCORD_BOT_TOKEN environment variable or use the --token argument.")
        sys.exit(1)
    
    # Set up asyncio event loop
    try:
        # Create a new event loop
        global event_loop
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        
        # Create Discord I/O Core
        discord_io = DiscordIOCore(token=token)
        
        # Create CLI tester
        cli_tester = DiscordCliTester(discord_io, event_loop)
        
        # Set event callback
        discord_io.set_event_callback(cli_tester.handle_event)
        
        # Start the Discord bot in a separate thread
        bot_thread = threading.Thread(target=discord_io.run)
        bot_thread.daemon = True
        bot_thread.start()
        
        try:
            # Start the CLI
            cli_tester.cmdloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            # Clean up
            cli_tester.running = False
    finally:
        # Stop the event loop
        if event_loop and event_loop.is_running():
            event_loop.stop()
        
        # Close the event loop
        if event_loop and not event_loop.is_closed():
            event_loop.close()

if __name__ == "__main__":
    main() 