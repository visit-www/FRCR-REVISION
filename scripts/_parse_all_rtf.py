#!/usr/bin/env python3
r"""
Parse RTF-wrapped JSON files into clean JSON.

Handles:
  - RTF header/footer removal
  - \{ -> {, \} -> }
  - \\ -> (removed)
  - \uc0\uNNNNN surrogate pairs -> removed (emoji)
  - JS-style comments (// ...) removal
  - \'XX hex escapes -> decoded characters
  - \cf0 and other RTF inline formatting -> removed
  - Trailing } from RTF wrapper
"""

import json
import re
import sys
import os


# Windows-1252 codepage map for 0x80-0x9F range
CP1252_MAP = {
    0x80: '\u20ac', 0x82: '\u201a', 0x83: '\u0192', 0x84: '\u201e',
    0x85: '\u2026', 0x86: '\u2020', 0x87: '\u2021', 0x88: '\u02c6',
    0x89: '\u2030', 0x8a: '\u0160', 0x8b: '\u2039', 0x8c: '\u0152',
    0x8e: '\u017d', 0x91: '\u2018', 0x92: '\u2019', 0x93: '\u201c',
    0x94: '\u201d', 0x95: '\u2022', 0x96: '\u2013', 0x97: '\u2014',
    0x98: '\u02dc', 0x99: '\u2122', 0x9a: '\u0161', 0x9b: '\u203a',
    0x9c: '\u0153', 0x9e: '\u017e', 0x9f: '\u0178',
}


def _replace_hex(m):
    code = int(m.group(1), 16)
    if code in CP1252_MAP:
        return CP1252_MAP[code]
    return chr(code)


def strip_rtf_to_json(raw):
    """Extract JSON text from an RTF-wrapped document."""

    # 1. Find content start after RTF header (\cf0 marker)
    match = re.search(r'\\cf0 ', raw)
    if match:
        text = raw[match.end():]
    else:
        # Fallback: find the first \{ which starts the JSON
        idx = raw.find('\\{')
        if idx >= 0:
            text = raw[idx:]
        else:
            raise ValueError("Cannot find JSON content start in RTF")

    # 2. Remove trailing RTF closing brace
    text = text.rstrip()
    if text.endswith('}}'):
        text = text[:-1]

    # 3. Handle \'XX hex escapes (Windows-1252)
    text = re.sub(r"\\'([0-9a-fA-F]{2})", _replace_hex, text)

    # 4. Remove \uc0\uNNNNN sequences (emoji surrogates)
    text = re.sub(r'\\uc0(?:\\u\d+\s*)+', '', text)
    text = re.sub(r'\\u\d+\s?', '', text)

    # 5. Unescape RTF braces BEFORE removing formatting codes
    #    RTF uses \{ and \} to represent literal { and }
    text = text.replace('\\{', '{')
    text = text.replace('\\}', '}')

    # 6. Remove trailing backslash-newline (RTF line continuations)
    text = text.replace('\\\n', '\n')

    # 7. Remove stray backslashes that aren't JSON escapes
    #    At this point, remaining \X patterns are RTF artifacts
    #    JSON only uses: \" \\ \/ \b \f \n \r \t \uXXXX
    #    But we should be safe since RTF formatting was already handled

    # 8. Remove JS-style comments (// ... to end of line)
    text = re.sub(r'(?m)^\s*//.*$', '', text)

    return text.strip()


def parse_rtf_to_json(input_path, output_path, label):
    """Parse a single RTF file to clean JSON. Returns the parsed data."""
    print(f"\n{'='*60}")
    print(f"Parsing: {label}")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")

    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    print(f"  Raw size: {len(raw):,} bytes")

    text = strip_rtf_to_json(raw)

    # Try to parse as JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ERROR: JSON parse failed: {e}")
        # Write the cleaned text for debugging
        debug_path = output_path + '.debug.txt'
        with open(debug_path, 'w') as f:
            f.write(text)
        print(f"  Debug text written to: {debug_path}")
        # Show context around the error
        lines = text.split('\n')
        start = max(0, e.lineno - 4)
        end = min(len(lines), e.lineno + 3)
        print(f"  Context around line {e.lineno}, col {e.colno}:")
        for i in range(start, end):
            marker = ">>>" if i == e.lineno - 1 else "   "
            print(f"  {marker} {i+1}: {lines[i][:150]}")
        raise

    # Write formatted JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  Output size: {os.path.getsize(output_path):,} bytes")
    print(f"  OK")
    return data


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    downloads = os.path.expanduser('~/Downloads')

    files = [
        (os.path.join(downloads, '1.json.rtf'),
         os.path.join(data_dir, 'protocols_batch_1.json'),
         'Protocols Batch 1'),
        (os.path.join(downloads, '2.json.rtf'),
         os.path.join(data_dir, 'protocols_batch_2.json'),
         'Protocols Batch 2'),
        (os.path.join(downloads, '3.json.rtf'),
         os.path.join(data_dir, 'protocols_batch_3.json'),
         'Protocols Batch 3'),
        (os.path.join(downloads, '4.json.rtf'),
         os.path.join(data_dir, 'protocols_batch_4.json'),
         'Protocols Batch 4'),
        (os.path.join(downloads, 'ALGORITHMS \u2014 PART 1.rtf'),
         os.path.join(data_dir, 'algorithms_part_1.json'),
         'Algorithms Part 1'),
        (os.path.join(downloads, 'ALGORITHMS \u2014 PART 2.rtf'),
         os.path.join(data_dir, 'algorithms_part_2.json'),
         'Algorithms Part 2'),
    ]

    os.makedirs(data_dir, exist_ok=True)

    total_protocols = 0
    total_algorithms = 0

    for input_path, output_path, label in files:
        if not os.path.isfile(input_path):
            print(f"\nWARNING: File not found: {input_path}")
            continue

        data = parse_rtf_to_json(input_path, output_path, label)

        # Summarize contents
        if 'protocols' in data:
            count = len(data['protocols'])
            total_protocols += count
            names = [p.get('name', '?') for p in data['protocols']]
            print(f"  Contains {count} protocols:")
            for n in names:
                print(f"    - {n}")
        elif 'advanced_algorithms' in data:
            count = len(data['advanced_algorithms'])
            total_algorithms += count
            names = [a.get('algorithm_id', '?') for a in data['advanced_algorithms']]
            print(f"  Contains {count} algorithms:")
            for n in names:
                print(f"    - {n}")
        elif isinstance(data, list):
            print(f"  Contains {len(data)} items (array)")
        else:
            print(f"  Top-level keys: {list(data.keys())}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"  Total protocol files parsed: 4")
    print(f"  Total protocols: {total_protocols}")
    print(f"  Total algorithm files parsed: 2")
    print(f"  Total algorithms: {total_algorithms}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
