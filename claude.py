#!/usr/bin/env python
"""
Claude CLI Client.

This script interacts with the Anthropic API to generate content based on
user input or existing conversation files.
"""

import argparse
import sys
from pathlib import Path
from typing import Iterable

import anthropic
from anthropic.types import MessageParam

from common import (
    StreamPrinter,
    create_conversation_context,
    create_parser,
    handle_streaming_error,
    run_conversation_loop,
)


def stream_claude_response(
    client: anthropic.Anthropic,
    model: str,
    messages: Iterable[MessageParam],
    args: argparse.Namespace,
) -> str:
    """Stream the response from the Claude API."""
    printer = StreamPrinter()
    assistant_content = []

    try:
        actual_max_tokens = int(args.max_tokens) if args.max_tokens else 20000

        with client.messages.stream(
            max_tokens=actual_max_tokens,
            messages=messages,
            model=model,
        ) as stream:
            for text in stream.text_stream:
                printer.write_content(text)
                assistant_content.append(text)

    except ConnectionError as e:
        handle_streaming_error(printer, e)

    printer.close()
    return "".join(assistant_content)


def main() -> None:
    "Main function"

    match Path(__file__).name:
        case "claude-opus" | "opus":
            model = "claude-opus-4-6"
        case "claude-haiku" | "haiku":
            model = "claude-haiku-4-5"
        case _:
            model = "claude-sonnet-4-6"

    parser = create_parser(
        description="Resume a conversation with Claude",
        model=model,
    )
    args = parser.parse_args()

    try:
        client = anthropic.Anthropic()
    except ConnectionError as e:
        sys.stderr.write(f"Error initializing Claude client: {e}\n")
        sys.stderr.write(
            "Ensure ANTHROPIC_API_KEY environment variable is set.\n"
        )
        sys.exit(1)

    context = create_conversation_context(args.conversation_file, args.model)

    run_conversation_loop(
        client,
        stream_claude_response,
        args,
        context,
    )


if __name__ == "__main__":
    main()
