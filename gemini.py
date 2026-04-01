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

from common import (
    StreamPrinter,
    create_parser,
    handle_streaming_error,
    load_conversation,
    run_conversation_loop,
)


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
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else msg["role"]
        part = Part.from_text(text=msg["content"])
        contents.append(Content(role=role, parts=[part]))

    try:
        config_kwargs: Dict[str, Any] = {
            "thinking_config": ThinkingConfig(
                thinking_level=ThinkingLevel.HIGH,
                include_thoughts=True,
            )
        }
        if args.max_tokens:
            config_kwargs["max_output_tokens"] = int(args.max_tokens)

        config = GenerateContentConfig(**config_kwargs)

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
        description="Resume a file specified filename",
        model="gemini-3.1-pro-preview",
    )
    args = parser.parse_args()

    client = genai.Client()

    filename, messages, file_hash = load_conversation(args.conversation_file)

    run_conversation_loop(
        client,
        stream_gemini_response,
        args.model,
        messages,
        args,
        filename,
        file_hash,
    )


if __name__ == "__main__":
    main()
