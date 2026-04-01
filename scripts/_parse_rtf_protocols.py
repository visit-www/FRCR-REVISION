#!/usr/bin/env python3
# Parse protocols.rtf -> imaging_protocols.json
#
# Handles RTF preamble stripping, escaped braces, JS-style comments,
# RTF unicode emoji escapes, RTF character escapes, and merging two
# separate protocol arrays into one flat output.

import json
import re
import sys
from pathlib import Path

SRC = Path.home() / "Downloads" / "protocols.rtf"
DST = Path(__file__).resolve().parent.parent / "data" / "imaging_protocols.json"


def strip_rtf(raw):
    # 1. Remove RTF preamble up to the font/color setup marker
    preamble_re = re.compile(
        r"^\{\\rtf1.*?\n\\f0\\fs\d+\s*\\cf0\s*", re.DOTALL
    )
    text = preamble_re.sub("", raw, count=1)

    # 2. Strip trailing RTF closing brace(s) at end of file
    text = text.rstrip()
    while text.endswith("}") and not text.endswith("\\}"):
        text = text[:-1].rstrip()

    # 3. Remove backslash-newline continuations (RTF line wrapping)
    text = text.replace("\\\n", "\n")

    # 4. Replace RTF-escaped braces
    text = text.replace("\\{", "{").replace("\\}", "}")

    # 5. Remove RTF unicode emoji escapes like \uc0\u55358 \u56800
    text = re.sub(r"\\uc0(?:\\u\d+\s*)+", "", text)
    text = re.sub(r"\\u\d+\s*", "", text)

    # 6. Handle RTF special character escapes
    text = text.replace("\\'96", "\u2013")   # en-dash
    text = text.replace("\\'97", "\u2014")   # em-dash
    text = text.replace("\\'b1", "\u00b1")   # plus-minus
    text = text.replace("\\'e9", "\u00e9")   # e-acute
    text = text.replace("\\'e8", "\u00e8")   # e-grave

    # 7. Strip garbage multi-hex and remaining 2-hex escapes
    text = re.sub(r"\\'[0-9a-fA-F]{4}", "", text)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)

    # 8. Remove JS-style // comment lines
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)

    # 9. Clean up any remaining RTF control words
    text = re.sub(r"\\[a-z]+\d*\s?", "", text)

    return text


def merge_protocol_arrays(text):
    objects = []
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : i + 1])
                start = None

    if not objects:
        print("ERROR: No JSON objects found after RTF stripping.", file=sys.stderr)
        sys.exit(1)

    all_protocols = []
    for idx, obj_str in enumerate(objects):
        try:
            obj = json.loads(obj_str)
        except json.JSONDecodeError as e:
            pos = e.pos or 0
            snippet = obj_str[max(0, pos - 80) : pos + 80]
            print(
                f"ERROR: JSON parse failed in object {idx + 1} at pos {pos}:\n"
                f"  {e.msg}\n"
                f"  ...{snippet!r}...",
                file=sys.stderr,
            )
            sys.exit(1)

        if "protocols" in obj:
            all_protocols.extend(obj["protocols"])
        else:
            print(
                f"WARNING: Object {idx + 1} has no 'protocols' key. Keys: {list(obj.keys())}",
                file=sys.stderr,
            )

    return all_protocols


def main():
    if not SRC.exists():
        print(f"ERROR: Source file not found: {SRC}", file=sys.stderr)
        sys.exit(1)

    raw = SRC.read_text(encoding="utf-8", errors="replace")
    print(f"Read {len(raw):,} bytes from {SRC}")

    clean = strip_rtf(raw)
    protocols = merge_protocol_arrays(clean)

    DST.parent.mkdir(parents=True, exist_ok=True)

    output = {"protocols": protocols}
    DST.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(protocols)} protocols to {DST}")


if __name__ == "__main__":
    main()
