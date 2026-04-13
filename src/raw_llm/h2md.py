#!/usr/bin/env python

"""Convert HTML to Markdown"""

import readline  # pylint: disable=unused-import
import sys
import argparse
from markdownify import markdownify as md


def convert(html_content):
    """Convert HTML content to Markdown"""
    return md(html_content).strip()


def main():
    """Main conversion function"""
    parser = argparse.ArgumentParser(description="Convert HTML to Markdown")
    parser.add_argument(
        "files",
        nargs="*",
        help="HTML files to convert (reads from stdin if not provided)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (prints to stdout if not provided)",
    )
    args = parser.parse_args()

    if args.files:
        contents = []
        for file_path in args.files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    contents.append(convert(f.read()))
            except FileNotFoundError:
                print(f"Error: File '{file_path}' not found.", file=sys.stderr)
                sys.exit(1)
            except OSError as e:
                print(f"Error reading '{file_path}': {e}", file=sys.stderr)
                sys.exit(1)
        result = "\n\n".join(contents)
    else:
        result = convert(sys.stdin.read())

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
        except OSError as e:
            print(f"Error writing to '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(result)


if __name__ == "__main__":
    main()
