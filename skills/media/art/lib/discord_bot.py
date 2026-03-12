#!/usr/bin/env python3

"""
discord_bot.py - Discord Bot Client for Midjourney Integration

Official Discord bot wrapper using discord.py for legitimate interaction
with Midjourney bot. Handles connection, message sending, monitoring,
and image downloads.

@see ~/.claude/skills/art/SKILL.md
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import discord
import httpx

# ============================================================================
# Constants
# ============================================================================

MIDJOURNEY_BOT_ID = 936929561302675456  # Official Midjourney bot ID

# ============================================================================
# Discord Bot Client
# ============================================================================


class DiscordBotClient:
    """Discord bot client for interacting with Midjourney."""

    def __init__(self, token: str, channel_id: str) -> None:
        self.token = token
        self.channel_id = channel_id
        self._connected = False

        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True

        self.client = discord.Client(intents=intents)
        self._ready_event = asyncio.Event()

        @self.client.event
        async def on_ready() -> None:
            print(f"Discord bot connected as {self.client.user}")
            self._connected = True
            self._ready_event.set()

        @self.client.event
        async def on_error(event: str, *args, **kwargs) -> None:  # type: ignore[override]
            print(f"Discord client error in {event}")

    async def connect(self) -> None:
        """Connect to Discord."""
        if self._connected:
            return

        # Start the client in a background task
        asyncio.create_task(self.client.start(self.token))
        # Wait for ready
        await self._ready_event.wait()

    async def send_message(self, content: str) -> discord.Message:
        """Send a message to the configured channel."""
        if not self._connected:
            raise RuntimeError("Bot not connected. Call connect() first.")

        channel = self.client.get_channel(int(self.channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(self.channel_id))

        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError(f"Channel {self.channel_id} is not a text channel")

        message = await channel.send(content)
        print(f"Sent message: {content}")
        return message

    async def wait_for_midjourney_response(
        self,
        initial_message_id: str,
        timeout: int,
        poll_interval: float = 5.0,
    ) -> discord.Message:
        """
        Wait for Midjourney's response to a prompt.

        Polls the channel for messages from Midjourney bot that reference
        our initial message. Returns when the response is complete.
        """
        import time

        start_time = time.time()
        timeout_ms = timeout

        print(f"Waiting for Midjourney response (timeout: {timeout}s)...")

        while time.time() - start_time < timeout_ms:
            channel = self.client.get_channel(int(self.channel_id))
            if channel is None:
                channel = await self.client.fetch_channel(int(self.channel_id))

            if not isinstance(channel, discord.TextChannel):
                raise RuntimeError("Channel not found or not text-based")

            messages = [msg async for msg in channel.history(limit=20)]

            for message in messages:
                # Check if message is from Midjourney bot
                if message.author.id != MIDJOURNEY_BOT_ID:
                    continue

                # Check if this references our initial prompt
                references_our_message = (
                    (message.reference and str(message.reference.message_id) == initial_message_id)
                    or (hasattr(message, "interaction") and message.interaction and str(message.interaction.id) == initial_message_id)
                    or initial_message_id in message.content
                )

                if not references_our_message:
                    continue

                if self._is_generation_complete(message):
                    print("Midjourney generation complete!")
                    return message
                else:
                    elapsed = int(time.time() - start_time)
                    print(f"Generation in progress... ({elapsed}s)")

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Timeout waiting for Midjourney response after {timeout}s")

    def _is_generation_complete(self, message: discord.Message) -> bool:
        """Check if Midjourney generation is complete."""
        if len(message.attachments) == 0:
            return False

        content = message.content.lower()
        in_progress_indicators = [
            "waiting to start",
            "(waiting)",
            "%)",
        ]
        # Also check individual low percentages
        for i in range(10):
            in_progress_indicators.append(f"({i}%)")

        return not any(ind in content for ind in in_progress_indicators)

    async def download_image(self, url: str, output_path: str) -> None:
        """Download image from URL to local path."""
        print(f"Downloading image from {url}...")

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url)
            response.raise_for_status()

        Path(output_path).write_bytes(response.content)
        print(f"Image saved to {output_path}")

    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        if not self._connected:
            return

        await self.client.close()
        self._connected = False
        print("Discord bot disconnected")

    def get_image_url(self, message: discord.Message) -> Optional[str]:
        """Get the first image attachment URL from a message."""
        if len(message.attachments) == 0:
            return None

        attachment = message.attachments[0]
        image_extensions = [".png", ".jpg", ".jpeg", ".webp", ".gif"]
        is_image = any(ext in attachment.url.lower() for ext in image_extensions)

        if not is_image:
            return None

        return attachment.url
