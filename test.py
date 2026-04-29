#!/usr/bin/env python3

import sys

TAG_BASE = 0xE0000
TAG_MIN = 0xE0000
TAG_MAX = 0xE007F


def encode_to_hidden_tags(text: str) -> str:
    """
    Convert ASCII text into Unicode tag characters.
    Example: 'TEST' -> hidden tag characters representing T E S T
    """
    output = []

    for char in text:
        code = ord(char)

        if code > 0x7F:
            raise ValueError(f"Only ASCII characters are supported. Unsupported character: {char!r}")

        output.append(chr(TAG_BASE + code))

    return "".join(output)


def decode_hidden_tags(text: str) -> str:
    """
    Decode Unicode tag characters back into normal ASCII text.
    Non-tag characters are ignored.
    """
    output = []

    for char in text:
        code = ord(char)

        if TAG_MIN <= code <= TAG_MAX:
            output.append(chr(code - TAG_BASE))

    return "".join(output)


def remove_hidden_tags(text: str) -> str:
    """
    Remove Unicode tag characters from text.
    """
    return "".join(char for char in text if not (TAG_MIN <= ord(char) <= TAG_MAX))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python hidden_tags.py encode 'TEST ONLY'")
        print("  python hidden_tags.py decode '<hidden text>'")
        print("  python hidden_tags.py clean '<text with hidden tags>'")
        sys.exit(1)

    mode = sys.argv[1]
    text = " ".join(sys.argv[2:])

    if mode == "encode":
        hidden = encode_to_hidden_tags(text)
        print(hidden)
        # write it to file
        filename = "hidden_tags_output.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(hidden)
        print(f"Hidden tags written to {filename}")
        print("\nDebug representation:")
        print(repr(hidden))

    elif mode == "decode":
        print(decode_hidden_tags(text))

    elif mode == "clean":
        print(remove_hidden_tags(text))

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
