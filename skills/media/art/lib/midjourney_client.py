#!/usr/bin/env python3

"""
midjourney_client.py - Midjourney Interaction Client

High-level client for interacting with Midjourney bot through Discord.
Handles prompt formatting, command submission, response parsing,
and error detection.

@see ~/.claude/skills/art/SKILL.md
"""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

import discord

from .discord_bot import DiscordBotClient

# ============================================================================
# Types
# ============================================================================

MidjourneyErrorType = Literal[
    "content_policy",
    "timeout",
    "connection",
    "invalid_params",
    "generation_failed",
    "no_image",
]


class MidjourneyError(Exception):
    """Midjourney-specific error with type, prompt, and suggestion."""

    def __init__(
        self,
        error_type: MidjourneyErrorType,
        message: str,
        original_prompt: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.original_prompt = original_prompt
        self.suggestion = suggestion


# ============================================================================
# Midjourney Client
# ============================================================================


class MidjourneyClient:
    """High-level client for Midjourney image generation via Discord."""

    def __init__(self, discord_bot: DiscordBotClient) -> None:
        self.discord_bot = discord_bot

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        version: str = "6.1",
        stylize: int = 100,
        quality: float = 1,
        chaos: Optional[int] = None,
        weird: Optional[int] = None,
        tile: bool = False,
        timeout: int = 120,
    ) -> dict[str, str]:
        """
        Generate an image with Midjourney.

        Returns dict with keys: image_url, prompt, message_id
        """
        formatted_prompt = self._format_prompt(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            version=version,
            stylize=stylize,
            quality=quality,
            chaos=chaos,
            weird=weird,
            tile=tile,
        )

        print(f"Submitting to Midjourney: {formatted_prompt}")

        # Send the /imagine command
        initial_message = await self.discord_bot.send_message(
            f"/imagine prompt: {formatted_prompt}"
        )

        # Wait for Midjourney to complete generation
        try:
            response_message = await self.discord_bot.wait_for_midjourney_response(
                initial_message_id=str(initial_message.id),
                timeout=timeout,
                poll_interval=5.0,
            )
        except TimeoutError:
            raise MidjourneyError(
                error_type="timeout",
                message=(
                    f"Generation timed out after {timeout}s. "
                    "The image may still be processing in Discord."
                ),
                original_prompt=formatted_prompt,
                suggestion="Try checking Discord manually or increasing the timeout value.",
            )

        # Check for errors in response
        self._detect_errors(response_message, formatted_prompt)

        # Extract image URL
        image_url = self.discord_bot.get_image_url(response_message)

        if not image_url:
            raise MidjourneyError(
                error_type="no_image",
                message="No image found in Midjourney response",
                original_prompt=formatted_prompt,
                suggestion="The generation may have failed. Check Discord for error messages.",
            )

        return {
            "image_url": image_url,
            "prompt": formatted_prompt,
            "message_id": str(response_message.id),
        }

    def _format_prompt(
        self,
        prompt: str,
        aspect_ratio: str,
        version: str,
        stylize: int,
        quality: float,
        chaos: Optional[int] = None,
        weird: Optional[int] = None,
        tile: bool = False,
    ) -> str:
        """Format Midjourney prompt with parameters."""
        formatted = prompt
        formatted += f" --ar {aspect_ratio}"
        formatted += f" --v {version}"

        if stylize != 100:
            formatted += f" --s {stylize}"
        if quality != 1:
            formatted += f" --q {quality}"
        if chaos is not None:
            formatted += f" --chaos {chaos}"
        if weird is not None:
            formatted += f" --weird {weird}"
        if tile:
            formatted += " --tile"

        return formatted

    def _detect_errors(
        self, message: discord.Message, original_prompt: str
    ) -> None:
        """Detect errors in Midjourney response."""
        content = message.content.lower()

        # Content policy violations
        content_policy_indicators = [
            "banned prompt",
            "content policy",
            "violates our community standards",
            "inappropriate content",
            "against our terms",
        ]
        for indicator in content_policy_indicators:
            if indicator in content:
                raise MidjourneyError(
                    error_type="content_policy",
                    message="Prompt violates Midjourney content policy",
                    original_prompt=original_prompt,
                    suggestion="Try rephrasing your prompt to avoid potentially sensitive content.",
                )

        # Invalid parameters
        invalid_param_indicators = [
            "invalid parameter",
            "unknown parameter",
            "invalid aspect ratio",
            "invalid version",
        ]
        for indicator in invalid_param_indicators:
            if indicator in content:
                raise MidjourneyError(
                    error_type="invalid_params",
                    message="Invalid Midjourney parameters",
                    original_prompt=original_prompt,
                    suggestion="Check your aspect ratio, version, and other parameter values.",
                )

        # Generation failures
        failure_indicators = [
            "failed to generate",
            "generation failed",
            "error generating",
            "something went wrong",
        ]
        for indicator in failure_indicators:
            if indicator in content:
                raise MidjourneyError(
                    error_type="generation_failed",
                    message="Midjourney generation failed",
                    original_prompt=original_prompt,
                    suggestion="Try again or check Discord for more details.",
                )

    def parse_response(
        self, message: discord.Message
    ) -> dict[str, Any]:
        """Parse Midjourney response to extract metadata."""
        content = message.content

        # Extract prompt (before the first --)
        prompt_match = re.match(r"^(.+?)(?:\s+--|\s*$)", content)
        prompt = prompt_match.group(1).strip() if prompt_match else content

        # Extract parameters
        parameters: dict[str, str] = {}
        for match in re.finditer(r"--(\w+)\s+([^\s-]+)", content):
            parameters[match.group(1)] = match.group(2)

        return {"prompt": prompt, "parameters": parameters}

    @staticmethod
    def validate_options(
        prompt: str = "",
        aspect_ratio: Optional[str] = None,
        version: Optional[str] = None,
        stylize: Optional[int] = None,
        quality: Optional[float] = None,
        chaos: Optional[int] = None,
        weird: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> None:
        """Validate Midjourney options before submission."""
        valid_aspect_ratios = [
            "1:1", "16:9", "9:16", "2:3", "3:2", "4:5", "5:4",
            "7:4", "4:7", "21:9", "9:21", "3:4", "4:3",
        ]
        if aspect_ratio and aspect_ratio not in valid_aspect_ratios:
            raise ValueError(
                f"Invalid aspect ratio: {aspect_ratio}. "
                f"Valid ratios: {', '.join(valid_aspect_ratios)}"
            )

        valid_versions = ["6.1", "6", "5.2", "5.1", "5", "niji", "niji 6"]
        if version and version not in valid_versions:
            raise ValueError(
                f"Invalid version: {version}. "
                f"Valid versions: {', '.join(valid_versions)}"
            )

        if stylize is not None and (stylize < 0 or stylize > 1000):
            raise ValueError("Stylize must be between 0 and 1000")

        valid_qualities = [0.25, 0.5, 1, 2]
        if quality is not None and quality not in valid_qualities:
            raise ValueError("Quality must be 0.25, 0.5, 1, or 2")

        if chaos is not None and (chaos < 0 or chaos > 100):
            raise ValueError("Chaos must be between 0 and 100")

        if weird is not None and (weird < 0 or weird > 3000):
            raise ValueError("Weird must be between 0 and 3000")

        if timeout is not None and timeout < 30:
            raise ValueError("Timeout must be at least 30 seconds")
