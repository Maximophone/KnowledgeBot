"""
Discord I/O Core Module - Handles Discord bot I/O operations without business logic.

This module provides a decoupled I/O interface for a Discord bot that handles message inputs
and actions, without any business logic. The business logic (brain) will be added later as a separate layer.
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional, Union
import discord
from discord import Message, User, DMChannel, TextChannel, Member
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_io")

class DiscordIOCore:
    """
    A decoupled I/O interface for a Discord bot that handles message inputs and actions,
    without any business logic.
    """

    def __init__(self, token: str):
        """
        Initialize Discord client with required intents.

        Args:
            token (str): The Discord bot token for authentication.
        """
        # Set up intents with privileged message intent enabled
        intents = discord.Intents.default()
        intents.message_content = True  # This is a privileged intent
        intents.members = True  # We need this to get user information

        # Initialize the Discord client
        self.client = discord.Client(intents=intents)
        self.token = token
        self.event_callback = None

        # Register event handlers
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    def set_event_callback(self, callback: Callable[[Dict[str, Any]], Any]):
        """
        Set a callback function to be called when an event occurs.
        
        Args:
            callback: A function that takes an event dictionary and processes it.
        """
        self.event_callback = callback

    async def on_ready(self):
        """Called when the client is done preparing the data received from Discord."""
        logger.info(f'Logged in as {self.client.user.name} ({self.client.user.id})')

    async def on_message(self, message: Message):
        """
        Handles incoming messages and routes them to the appropriate handler.
        
        Args:
            message (discord.Message): The incoming message object.
        """
        # Ignore messages from ourselves
        if message.author.id == self.client.user.id:
            return

        # Handle direct messages
        if isinstance(message.channel, DMChannel):
            event = await self._on_dm(message)
            if self.event_callback:
                await self.event_callback(event)
            return

        # Handle mentions in guild channels
        if self.client.user in message.mentions:
            event = await self._on_mention(message)
            if self.event_callback:
                await self.event_callback(event)
            return

    async def _on_dm(self, message: Message) -> Dict[str, Any]:
        """
        Format DM event.
        
        Args:
            message (discord.Message): The direct message object.
            
        Returns:
            dict: A dictionary with event data: {'type': 'dm', 'user_id': str, 'text': str, ...}
        """
        return {
            'type': 'dm',
            'user_id': str(message.author.id),
            'text': message.content,
            'timestamp': message.created_at.isoformat(),
            'author_name': message.author.name,
            'message_id': str(message.id)
        }

    async def _on_mention(self, message: Message) -> Dict[str, Any]:
        """
        Format mention event.
        
        Args:
            message (discord.Message): The message with a mention.
            
        Returns:
            dict: A dictionary with event data: {'type': 'mention', 'channel_id': str, ...}
        """
        return {
            'type': 'mention',
            'user_id': str(message.author.id),
            'channel_id': str(message.channel.id),
            'guild_id': str(message.guild.id),
            'text': message.content,
            'timestamp': message.created_at.isoformat(),
            'author_name': message.author.name,
            'message_id': str(message.id)
        }

    async def send_dm(self, user_id: int, text: str) -> bool:
        """
        Send DM to user.
        
        Args:
            user_id (int): The ID of the user to send a DM to.
            text (str): The message text to send.
            
        Returns:
            bool: Success status.
        """
        try:
            # Validate user ID
            if not isinstance(user_id, int):
                user_id = int(user_id)
                
            # Get the user and send the message
            for _ in range(3):  # Retry 3 times
                try:
                    user = await self.client.fetch_user(user_id)
                    await user.send(text)
                    return True
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = e.retry_after
                        logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                    else:
                        raise
            
            return False
        except Exception as e:
            logger.error(f"Error sending DM to user {user_id}: {str(e)}")
            return False

    async def post_message(self, channel_id: int, text: str) -> bool:
        """
        Post to channel.
        
        Args:
            channel_id (int): The ID of the channel to post to.
            text (str): The message text to post.
            
        Returns:
            bool: Success status.
        """
        try:
            # Validate channel ID
            if not isinstance(channel_id, int):
                channel_id = int(channel_id)
                
            # Get the channel and send the message
            for _ in range(3):  # Retry 3 times
                try:
                    channel = await self.client.fetch_channel(channel_id)
                    if not isinstance(channel, (TextChannel, DMChannel)):
                        logger.error(f"Channel {channel_id} is not a text channel")
                        return False
                    
                    await channel.send(text)
                    return True
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = e.retry_after
                        logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                    else:
                        raise
            
            return False
        except Exception as e:
            logger.error(f"Error posting message to channel {channel_id}: {str(e)}")
            return False

    async def read_recent_messages(self, channel_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get last N messages from channel.
        
        Args:
            channel_id (int): The ID of the channel to read messages from.
            limit (int, optional): Maximum number of messages to retrieve. Defaults to 100.
            
        Returns:
            list[dict]: A list of message dictionaries.
        """
        try:
            # Validate channel ID and limit
            if not isinstance(channel_id, int):
                channel_id = int(channel_id)
                
            if limit > 100:
                limit = 100  # Discord API limit
                
            # Get the channel and retrieve messages
            for _ in range(3):  # Retry 3 times
                try:
                    channel = await self.client.fetch_channel(channel_id)
                    if not isinstance(channel, (TextChannel, DMChannel)):
                        logger.error(f"Channel {channel_id} is not a text channel")
                        return []
                    
                    messages = []
                    async for msg in channel.history(limit=limit):
                        messages.append({
                            'content': msg.content,
                            'author_id': str(msg.author.id),
                            'author_name': msg.author.name,
                            'timestamp': msg.created_at.isoformat(),
                            'message_id': str(msg.id)
                        })
                    
                    return messages
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = e.retry_after
                        logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                    else:
                        raise
            
            return []
        except Exception as e:
            logger.error(f"Error reading messages from channel {channel_id}: {str(e)}")
            return []

    async def read_user_dm_history(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get last N DMs with specific user.
        
        Args:
            user_id (int): The ID of the user to get DM history with.
            limit (int, optional): Maximum number of messages to retrieve. Defaults to 100.
            
        Returns:
            list[dict]: A list of message dictionaries.
        """
        try:
            # Validate user ID and limit
            if not isinstance(user_id, int):
                user_id = int(user_id)
                
            if limit > 100:
                limit = 100  # Discord API limit
                
            # Get the user and their DM channel
            for _ in range(3):  # Retry 3 times
                try:
                    user = await self.client.fetch_user(user_id)
                    dm_channel = user.dm_channel
                    
                    # Create DM channel if it doesn't exist
                    if dm_channel is None:
                        dm_channel = await user.create_dm()
                    
                    messages = []
                    async for msg in dm_channel.history(limit=limit):
                        messages.append({
                            'content': msg.content,
                            'author_id': str(msg.author.id),
                            'author_name': msg.author.name,
                            'timestamp': msg.created_at.isoformat(),
                            'message_id': str(msg.id)
                        })
                    
                    return messages
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = e.retry_after
                        logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                    else:
                        raise
            
            return []
        except Exception as e:
            logger.error(f"Error reading DM history with user {user_id}: {str(e)}")
            return []

    async def start_bot(self):
        """Start the Discord bot and connect to Discord."""
        await self.client.start(self.token)

    def run(self):
        """Run the Discord bot (blocking)."""
        self.client.run(self.token)

    async def close(self):
        """Close the connection to Discord and cleanup."""
        await self.client.close()
        
    async def reconnect(self):
        """Reconnect the Discord bot to Discord's servers."""
        try:
            logger.info("Attempting to reconnect Discord bot...")
            # Close the existing client connection
            await self.client.close()
            
            # We need to recreate intents and the client
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True
            
            # Create a new client instance
            self.client = discord.Client(intents=intents)
            
            # Re-register event handlers
            self.client.event(self.on_ready)
            self.client.event(self.on_message)
            
            # Start the bot with the token
            await self.client.login(self.token)
            
            # Send a ready event through the callback
            if self.event_callback:
                ready_event = {
                    'type': 'ready',
                    'timestamp': datetime.now().isoformat(),
                    'bot_name': self.client.user.name,
                    'bot_id': str(self.client.user.id)
                }
                await self.event_callback(ready_event)
                
            # Return success
            return True
        except Exception as e:
            logger.error(f"Error during reconnection: {str(e)}")
            return False 