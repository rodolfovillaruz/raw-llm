#!/usr/bin/env python
"""
Claude CLI Client.

This script interacts with the Anthropic API to generate content based on
user input or existing conversation files.
"""

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import anthropic
from anthropic.types import (
    MessageParam,
    ThinkingConfigAdaptiveParam,
    ThinkingConfigEnabledParam,
)

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


def _build_thinking_config(
    model: str, max_tokens: int
) -> ThinkingConfigEnabledParam | ThinkingConfigAdaptiveParam:
    """
    Return the appropriate thinking configuration for the given model.

    Claude Opus 4.7 and later models no longer accept manual extended thinking
    (type: "enabled" with budget_tokens) and return a 400 error.  These models
    require adaptive thinking instead.  For Claude Opus 4.6 and Sonnet 4.6,
    manual mode is deprecated but still functional.
    """
    # Opus 4.7+ requires adaptive thinking; older opus (4.6) still accepts
    # manual mode.  The startswith guard also covers future opus releases
    # (4.8, 5.0, …) which will likewise require adaptive thinking.
    if model.startswith("claude-opus") and not model.startswith(
        "claude-opus-4-6"
    ):
        return {"type": "adaptive"}

    budget_tokens = max(max_tokens - 1024, 1024)
    return {
        "type": "enabled",
        "budget_tokens": budget_tokens,
    }


def stream_claude_response(
    client: anthropic.Anthropic,
    model: str,
    messages: Iterable[MessageParam],
    max_tokens: int,
) -> Tuple[str, Dict[str, int]]:
    """
    Stream the response from the Claude API with extended thinking.

    Returns a ``(content, usage)`` tuple where *usage* is a dict with
    ``input`` and ``output`` token counts.
    """
    printer = StreamPrinter()
    assistant_content: List[str] = []
    input_tokens = 0
    output_tokens = 0

    try:
        actual_max_tokens = int(max_tokens) if max_tokens else 20000
        thinking_config = _build_thinking_config(model, actual_max_tokens)

        with client.messages.stream(
            max_tokens=actual_max_tokens,
            messages=messages,
            model=model,
            thinking=thinking_config,
        ) as stream:
            for event in stream:
                if event.type == "message_start":
                    # input_tokens is known as soon as the response begins
                    input_tokens = event.message.usage.input_tokens
                elif event.type == "message_delta":
                    # output_tokens is finalised in the closing delta
                    output_tokens = event.usage.output_tokens
                elif event.type == "content_block_start":
                    if event.content_block.type == "thinking":
                        printer.write_reasoning("")  # activate reasoning color
                elif event.type == "content_block_delta":
                    if event.delta.type == "thinking_delta":
                        printer.write_reasoning(event.delta.thinking)
                    elif event.delta.type == "text_delta":
                        printer.write_content(event.delta.text)
                        assistant_content.append(event.delta.text)

    except ConnectionError as e:
        printer.close()
        sys.stderr.write(f"\nError during streaming: {e}\n")
        sys.exit(1)

    printer.close()
    usage = {"input": input_tokens, "output": output_tokens}
    return "".join(assistant_content), usage


def main() -> None:
    "Main function"

    command_name = Path(sys.argv[0]).name.lower()

    match command_name:
        case "claude-opus" | "opus":
            model = "claude-opus-4-7"
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

    filename, messages, file_hash = load_conversation(args.conversation_file)

    sys.stderr.write(f"Model: {args.model}\n\n")
    sys.stderr.flush()

    question = get_question()
    if not question:
        raise ValueError("No messages to send")

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

    # strip_metadata produces a clean List[MessageParam] the API accepts
    assistant_content, usage = stream_claude_response(
        client, args.model, strip_metadata(messages), args.max_tokens
    )

    messages.append(
        {
            "role": "assistant",
            "content": assistant_content,
            "timestamp": now_utc(),
            "usage": {"input": usage["input"], "output": usage["output"]},
            "model": args.model,
        }
    )

    sys.stderr.write("\n")
    sys.stderr.flush()

    save_conversation_safely(messages, filename, file_hash)


if __name__ == "__main__":
    main()
