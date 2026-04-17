#!/usr/bin/env python
"""
Gemini CLI Client.

This script interacts with the Google GenAI API to generate content based on
user input or existing conversation files.
"""

import sys
from typing import Any, Dict, List

from google import genai
from google.genai.types import (
    Content,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    ThinkingLevel,
)

from .common import (
    StreamPrinter,
    create_parser,
    get_question,
    load_conversation,
    prompt_preview,
    save_conversation_safely,
)


def stream_gemini_response(
    client: genai.Client,
    model: str,
    contents: list[Content],  # Changed from Sequence[Content]
    config: GenerateContentConfig,
) -> str:
    """
    Stream the response from the Gemini API, printing reasoning to stderr
    and content to stdout. Returns the full assistant content.
    """
    printer = StreamPrinter()
    assistant_parts = []

    try:
        stream = client.models.generate_content_stream(
            contents=contents,  # type: ignore[arg-type]
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
                    # Gemini marks reasoning with the 'thought' attribute
                    if getattr(part, "thought", False):
                        printer.write_reasoning(text)
                    else:
                        printer.write_content(text)
                        assistant_parts.append(text)

    except ConnectionError as e:
        printer.close()
        sys.stderr.write(f"\nError during streaming: {e}\n")
        sys.exit(1)

    printer.close()
    return "".join(assistant_parts)


def main() -> None:
    "Main function"

    parser = create_parser(
        description="Resume a file specified filename",
        model="gemini-3.1-pro-preview",
    )
    args = parser.parse_args()

    # Initialize Gemini client
    client = genai.Client()

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

    messages.append({"role": "user", "content": question})

    if args.dry_run:
        sys.exit(0)

    # Build Gemini Content objects
    contents: List[Content] = []
    for msg in messages:
        role_str: str = "model" if msg["role"] == "assistant" else msg["role"]

        content = msg["content"]
        if isinstance(content, str):
            text_content = content
        else:
            text_content = str(content)

        part = Part.from_text(text=text_content)
        contents.append(Content(role=role_str, parts=[part]))

    config_kwargs: Dict[str, Any] = {
        "thinking_config": ThinkingConfig(
            thinking_level=ThinkingLevel.HIGH,
            include_thoughts=True,
        )
    }
    if args.max_tokens:
        config_kwargs["max_output_tokens"] = int(args.max_tokens)

    config = GenerateContentConfig(**config_kwargs)

    assistant_content = stream_gemini_response(
        client, args.model, contents, config
    )

    messages.append({"role": "assistant", "content": assistant_content})

    sys.stderr.write("\n")
    sys.stderr.flush()

    save_conversation_safely(messages, filename, file_hash)


if __name__ == "__main__":
    main()
