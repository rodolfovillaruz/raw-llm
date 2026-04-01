"""Common utilities for AI conversation tools."""

import argparse
import contextlib
import hashlib
import itertools
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from anthropic.types import MessageParam

# Try to import readline for better input line editing (Unix only)
try:
    import readline  # noqa: F401  # pylint: disable=unused-import
except ImportError:
    pass

PROMPT_FOLDER = ".prompt"
EMPTY_HASH = hashlib.sha256(b"").hexdigest()


def spinner_task(
    spinner_chars: itertools.cycle, done: threading.Event, label: str
) -> None:
    """Show a spinner animation on stderr until done event is set."""
    start = time.perf_counter()
    for char in spinner_chars:
        elapsed = time.perf_counter() - start
        sys.stderr.write(f"\r\033[K{label} {char} ({elapsed:.1f}s)")
        sys.stderr.flush()
        if done.wait(0.1):
            break
    elapsed = time.perf_counter() - start
    sys.stderr.write(f"\r\033[K{label} done ({elapsed:.1f}s)\n")
    sys.stderr.flush()


@contextlib.contextmanager
def spinning(label: str = "Working"):
    """Context manager that displays a spinner while code executes."""
    spinner = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    done_flag = threading.Event()
    thread = threading.Thread(
        target=spinner_task, args=(spinner, done_flag, label), daemon=True
    )
    thread.start()
    try:
        yield
    finally:
        done_flag.set()
        thread.join()


def ask_yes_no(prompt: str) -> bool:
    """Return True if the user answers 'y' or 'yes' (case-insensitive)."""
    sys.stderr.write(f"{prompt} [y/N] ")
    sys.stderr.flush()
    answer = input().strip().lower()
    return answer.startswith("y")


def ask_filename(default: str) -> Path:
    """
    Ask for a filename.
    If the file already exists the user is asked whether to overwrite it.
    The question is repeated until a valid answer is given.
    """
    while True:
        sys.stderr.write(f"\nFilename [{default}]: ")
        sys.stderr.flush()
        name = input().strip() or default

        if not os.path.exists(name):
            return Path(name)

        sys.stderr.write(f'File "{name}" exists. Overwrite? [y/N]: ')
        sys.stderr.flush()
        choice = input().strip().lower()
        if choice in {"y", "yes"}:
            return Path(name)


def same_hash(path: Path, old_hash: str) -> bool:
    """True -> file still has the same sha256 we saw when we loaded it."""
    return old_hash == hashlib.sha256(path.read_bytes()).hexdigest()


def get_question() -> str:
    """Read question from stdin without stripping."""
    if sys.stdin.isatty():
        sys.stderr.write("Press Ctrl+D to submit\n\n")
        sys.stderr.flush()
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)

    # Non-interactive: read entire stdin
    return sys.stdin.read()


def get_width() -> int:
    """Get terminal width"""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def prompt_preview(prompt: str):
    """Preview prompt with visual markers"""
    width = get_width()
    start = "[ PROMPT ] "
    end = "[ / PROMPT ] "
    asterisks_start = "*" * (width - len(start))
    asterisks_end = "*" * (width - len(end))
    sys.stderr.write(
        "\n".join(
            [
                start + asterisks_start,
                prompt.rstrip(),
                end + asterisks_end + "\n\n",
            ]
        )
    )
    sys.stderr.flush()


def create_parser(description: str, model: str) -> argparse.ArgumentParser:
    """Create an argument parser with common arguments."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "conversation_file", nargs="?", default=None, help="Conversation file"
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="Run without submitting"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (-v = INFO, -vv = DEBUG)",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=model,
        help="Name or identifier of the model to use",
    )
    parser.add_argument(
        "-t",
        "--max-tokens",
        type=str,
        help="Maximum number of tokens that can be generated in the response.",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive REPL mode (each line is a separate message)",
    )
    return parser


def load_conversation(
    filepath_arg: Optional[str],
) -> Tuple[Path, List[MessageParam], str]:
    "Load conversation from file or create new file path if it does not exist."

    if not filepath_arg:
        if os.path.isdir(PROMPT_FOLDER):
            filename = (Path(PROMPT_FOLDER) / str(uuid.uuid1())).with_suffix(
                ".json"
            )
        else:
            filename = Path(str(uuid.uuid1())).with_suffix(".json")
    else:
        filename = Path(filepath_arg)

    try:
        with filename.open(encoding="utf-8") as fh:
            content_str = fh.read()
            json_content = json.loads(content_str)
            file_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    except FileNotFoundError:
        file_hash = EMPTY_HASH
        json_content = []
    except (json.JSONDecodeError, ValueError) as exc:
        raise AssertionError(
            f"Content of '{filename}' is not valid JSON: {exc}"
        ) from exc

    return filename, json_content, file_hash


def save_to_file(messages: list[MessageParam], filename: Path) -> Path:
    """Save messages to JSON file."""
    with filename.open("w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    return filename


def save_conversation_safely(
    messages: List[MessageParam], filename: Path, original_hash: str
) -> None:
    "Save conversation to file if it hasn't been modified elsewhere."

    if original_hash == EMPTY_HASH:
        save_to_file(messages, filename)
        sys.stderr.write(f"\nSaved to {filename}\n")
    elif same_hash(filename, original_hash):
        save_to_file(messages, filename)
        sys.stderr.write(f"\nSaved to {filename}\n")
    else:
        sys.stderr.write(
            f"\nError: “{filename}” has been modified by another process.\n"
        )
        sys.exit(2)


def get_colors() -> Dict[str, str]:
    """
    Return color escape sequences for reasoning and content output,
    empty strings if the corresponding stream is not a terminal.
    """
    colors = {}
    if sys.stderr.isatty():
        colors["reasoning"] = "\033[90m"
        colors["reasoning_reset"] = "\033[0m"
    else:
        colors["reasoning"] = colors["reasoning_reset"] = ""
    if sys.stdout.isatty():
        colors["content"] = "\033[36m"
        colors["content_reset"] = "\033[0m"
    else:
        colors["content"] = colors["content_reset"] = ""
    return colors


def run_conversation_loop(
    client: Any,
    stream_func: callable,
    model: str,
    messages: List[MessageParam],
    args: argparse.Namespace,
    filename: Path,
    file_hash: str,
) -> None:
    """
    Unified conversation loop for Claude and Gemini clients.

    Args:
        client: The API client (Anthropic or Google GenAI)
        stream_func: Function that streams the response
        model: Model name/identifier
        messages: Conversation messages
        args: Parsed command-line arguments
        filename: Conversation file path
        file_hash: Original file hash for safety check
    """
    if args.verbose > 0:
        sys.stderr.write(f"Model: {model}\n\n")
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

    assistant_content = stream_func(client, model, messages, args)

    messages.append({"role": "assistant", "content": assistant_content})

    sys.stderr.write("\n")
    sys.stderr.flush()

    save_conversation_safely(messages, filename, file_hash)


def handle_streaming_error(
    printer: StreamPrinter, error: ConnectionError
) -> None:
    """Handle connection errors during streaming."""
    printer.close()
    sys.stderr.write(f"\nError during streaming: {error}\n")
    sys.exit(1)


class StreamPrinter:
    """Handles colored output of reasoning and content streams."""

    def __init__(self):
        self.colors = get_colors()
        self.reasoning_active = False
        self.content_active = False

    def write_reasoning(self, text: str) -> None:
        """Write reasoning text to stderr with appropriate coloring."""
        if not self.reasoning_active:
            sys.stderr.write(self.colors["reasoning"])
            self.reasoning_active = True
        sys.stderr.write(text)
        sys.stderr.flush()

    def write_content(self, text: str) -> None:
        """Write content text to stdout with appropriate coloring."""
        if self.reasoning_active:
            sys.stderr.write(self.colors["reasoning_reset"])
            sys.stderr.flush()
            self.reasoning_active = False
        if not self.content_active:
            sys.stdout.write(self.colors["content"])
            self.content_active = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def close(self) -> None:
        """Reset colors if any were active."""
        if self.reasoning_active:
            sys.stderr.write(self.colors["reasoning_reset"])
            sys.stderr.flush()
        if self.content_active:
            sys.stdout.write(self.colors["content_reset"])
            sys.stdout.flush()
