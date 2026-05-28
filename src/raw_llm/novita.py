#!/usr/bin/env python
"""
Novita AI CLI Client.

This script interacts with the Novita AI API (OpenAI-compatible) to generate
content based on user input or existing conversation files.
"""

import os
import sys
from typing import Dict, List, Tuple

from openai import OpenAI

from .common import (
    StreamPrinter,
    create_parser,
    get_question,
    load_conversation,
    now_utc,
    prompt_preview,
    save_conversation_safely,
    strip_metadata,
)

NOVITA_BASE_URL = "https://api.novita.ai/openai"


def stream_novita_response(
    client: OpenAI,
    model: str,
    messages: List[Dict],
    max_tokens: int | None,
) -> Tuple[str, Dict[str, int]]:
    """
    Stream the response from the Novita API, printing reasoning to stderr
    and content to stdout.

    Returns a ``(content, usage)`` tuple where *usage* is a dict with
    ``input`` and ``output`` token counts.
    """
    printer = StreamPrinter()
    assistant_parts: List[str] = []
    input_tokens = 0
    output_tokens = 0

    try:
        kwargs: Dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens:
            kwargs["max_tokens"] = int(max_tokens)

        stream = client.chat.completions.create(**kwargs)

        for chunk in stream:
            # Usage information arrives in the final chunk
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # DeepSeek models expose chain-of-thought via reasoning_content
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                printer.write_reasoning(reasoning)

            if delta.content:
                printer.write_content(delta.content)
                assistant_parts.append(delta.content)

    except ConnectionError as e:
        printer.close()
        sys.stderr.write(f"\nError during streaming: {e}\n")
        sys.exit(1)

    printer.close()
    usage = {"input": input_tokens, "output": output_tokens}
    return "".join(assistant_parts), usage


def main() -> None:
    """Main function"""

    parser = create_parser(
        description="Resume a conversation with Novita AI (DeepSeek)",
        model="deepseek/deepseek-v4-pro",
    )
    args = parser.parse_args()

    # Prefer NOVITA_API_KEY
    api_key = os.environ.get("NOVITA_API_KEY")
    if not api_key:
        sys.stderr.write(
            "Error: set NOVITA_API_KEY"
            "environment variable.\n"
        )
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=NOVITA_BASE_URL)

    filename, messages, file_hash = load_conversation(args.conversation_file)

    sys.stderr.write(f"Model: {args.model}\n\n")
    sys.stderr.flush()

    question = get_question()
    if not question:
        raise ValueError("No messages to send")

    if not args.no_strip:
        question = question.rstrip()

    sys.stderr.write("\n")
    sys.stderr.flush()

    if args.verbose > 0:
        prompt_preview(question)

    messages.append(
        {
            "role": "user",
            "content": question,
            "timestamp": now_utc(),
        }
    )

    if args.dry_run:
        sys.exit(0)

    assistant_content, usage = stream_novita_response(
        client, args.model, strip_metadata(messages), args.max_tokens
    )

    messages.append(
        {
            "role": "assistant",
            "content": assistant_content,
            "timestamp": now_utc(),
            "usage": {"input": usage["input"], "output": usage["output"]},
            "model": args.model,
            "library": "OpenAI",
            "endpoint": NOVITA_BASE_URL,
        }
    )

    sys.stderr.write("\n")
    sys.stderr.flush()

    save_conversation_safely(messages, filename, file_hash)


if __name__ == "__main__":
    main()
