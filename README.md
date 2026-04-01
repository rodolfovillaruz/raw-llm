# Simple

**The simplest way to context engineer.**

Minimal, streaming CLI clients for Claude and Gemini that keep your conversations in plain JSON files.

## What is this?

Simple is a pair of thin Python scripts that talk to the Anthropic and Google GenAI APIs. No frameworks, no agents, no abstractions you don't need. Just a prompt, a streaming response, and a JSON file you can version, diff, edit, and pipe.

The entire idea: your conversation _is_ a file. You build context by editing that file. That's it. That's the context engineering.

## Features

- **Streaming output** — responses print token-by-token as they arrive
- **Conversation persistence** — every exchange is saved to a plain JSON file you own
- **Resume any conversation** — pass the JSON file back in to continue where you left off
- **Pipe-friendly** — reads from stdin, writes content to stdout, writes diagnostics to stderr
- **Colored output** — reasoning in gray (stderr), content in cyan (stdout), auto-disabled when piped
- **Conflict detection** — refuses to overwrite a conversation file modified by another process
- **Symlink to switch models** — symlink `claude.py` as `opus` or `haiku` to change the default model

## Installation

```bash
git clone https://github.com/rodolfovillaruz/simple.git
cd simple
pip install anthropic google-genai
```

Set your API keys:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="..."       # or GOOGLE_API_KEY, per google-genai docs
```

## Usage

### Start a new conversation

```bash
python claude.py
# Type your prompt, then press Ctrl+D to submit
```

```bash
echo "Explain monads in one paragraph" | python claude.py
```

```bash
python gemini.py
```

### Resume an existing conversation

```bash
python claude.py .prompt/some-conversation.json
```

The JSON file contains the full message history. Edit it with any text editor to reshape context before your next turn.

### Pipe a file as context

```bash
cat code.py | python claude.py conversation.json
```

### Switch models

```bash
# By flag
python claude.py -m claude-opus-4-6

# By symlink
ln -s claude.py opus
./opus
```

| Symlink name         | Default model          |
| -------------------- | ---------------------- |
| `claude.py` (default)| `claude-sonnet-4-6`    |
| `claude-opus` / `opus`| `claude-opus-4-6`     |
| `claude-haiku` / `haiku`| `claude-haiku-4-5`  |
| `gemini.py` (default)| `gemini-3.1-pro-preview` |

### Options

```
usage: claude.py [-h] [-n] [-v] [-m MODEL] [-t MAX_TOKENS] [-i] [conversation_file]

positional arguments:
  conversation_file         JSON file to resume (omit to start fresh)

options:
  -n, --dry-run             Build the prompt but don't send it
  -v, --verbose             Show model name and prompt preview
  -m, --model MODEL         Override the default model
  -t, --max-tokens TOKENS   Cap the response length
  -i, --interactive         Interactive REPL mode
```

## Conversation format

Conversations are stored as a JSON array of message objects, the same shape both APIs understand:

```json
[
  {
    "role": "user",
    "content": "What is context engineering?"
  },
  {
    "role": "assistant",
    "content": "Context engineering is the practice of ..."
  }
]
```

You can create these files by hand, merge them, truncate them, or generate them with other tools. Simple doesn't care. It reads the array, appends your new message, streams the response, and appends that too.

## Project structure

```
.
├── claude.py       # Claude CLI client
├── gemini.py       # Gemini CLI client
├── common.py       # Shared utilities (streaming, I/O, conversation management)
├── Makefile        # Formatting, linting, typing
└── .prompt/        # Default directory for conversation files (auto-used if present)
```

## Development

```bash
make fmt      # Format with black/isort
make lint     # Lint with pylint/flake8
make type     # Type-check with mypy
make all      # All of the above
```

## Why?

Most LLM tools add layers between you and the model. Simple removes them. The conversation is a file. The prompt is stdin. The response is stdout. Everything else is up to you.

## License

MIT