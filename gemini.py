#!/usr/bin/env python
"""
Gemini CLI Client.

This script interacts with the Google GenAI API to generate content based on
user input or existing conversation files.
"""

import argparse
from typing import Any, Dict, List

from google import genai
from google.genai.types import (
    Content,
    GenerateContentConfig,
    MessageParam,
    Part,
    ThinkingConfig,
    ThinkingLevel,
)

from common import create_conversation_context  # Add this import
from common import (
    StreamPrinter,
    create_parser,
    handle_streaming_error,
    run_conversation_loop,
)


def _build_gemini_config(args: argparse.Namespace) -> GenerateContentConfig:
    """Build Gemini generation config from arguments."""
    config_kwargs: Dict[str, Any] = {
        "thinking_config": ThinkingConfig(
            thinking_level=ThinkingLevel.HIGH,
            include_thoughts=True,
        )
    }
    if args.max_tokens:
        config_kwargs["max_output_tokens"] = int(args.max_tokens)
    return GenerateContentConfig(**config_kwargs)


def stream_gemini_response(
    client: genai.Client,
    model: str,
    messages: List[MessageParam],
    args: argparse.Namespace,
) -> str:
    """Stream the response from the Gemini API."""
    printer = StreamPrinter()
    assistant_parts = []

    # Convert messages to Gemini Content objects
    contents = [
        Content(
            role="model" if msg["role"] == "assistant" else msg["role"],
            parts=[Part.from_text(text=msg["content"])],
        )
        for msg in messages
    ]

    try:
        config = _build_gemini_config(args)
        stream = client.models.generate_content_stream(
            contents=contents,
            model=model,
            config=config,
        )

        for chunk in stream:
            if not chunk.candidates:
                continue
            for candidate in chunk.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    text = part.text
                    if not text:
                        continue
                    if getattr(part, "thought", False):
                        printer.write_reasoning(text)
                    else:
                        printer.write_content(text)
                        assistant_parts.append(text)

    except ConnectionError as e:
        handle_streaming_error(printer, e)

    printer.close()
    return "".join(assistant_parts)


def main() -> None:
    "Main function"

    parser = create_parser(
        description="Resume a conversation with Gemini",
        model="gemini-3.1-pro-preview",
    )
    args = parser.parse_args()

    client = genai.Client()

    context = create_conversation_context(args.conversation_file, args.model)

    run_conversation_loop(
        client,
        stream_gemini_response,
        args,
        context,
    )


if __name__ == "__main__":
    main()
