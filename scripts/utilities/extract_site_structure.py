import json
from urllib.parse import urlparse
from collections import defaultdict
import os

def build_tree(paths):
    tree = lambda: defaultdict(tree)
    root = tree()
    for path in paths:
        parts = [p for p in path.split("/") if p]
        current = root
        for part in parts:
            current = current[part]
    return root

def print_tree(tree, prefix=""):
    keys = sorted(tree.keys())
    for i, key in enumerate(keys):
        connector = "└── " if i == len(keys) - 1 else "├── "
        print(prefix + connector + key)
        extension = "    " if i == len(keys) - 1 else "│   "
        print_tree(tree[key], prefix + extension)

def suggest_filename(base_url):
    domain = urlparse(base_url).netloc.replace(".", "")
    return f"{domain}_sites.json"

def main():
    base_url = input(
        "Enter base website URL (e.g. https://ajccstaging.org): "
    ).strip()

    if not base_url:
        print("❌ Base URL is required.")
        return

    suggested_file = suggest_filename(base_url)
    file_input = input(
        f"Enter JSON filename [suggested: {suggested_file}]: "
    ).strip()

    json_file = file_input if file_input else suggested_file

    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        return

    base_domain = urlparse(base_url).netloc

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    paths = set()

    for entry in data:
        url = entry.get("url")
        if not url:
            continue

        parsed = urlparse(url)

        if parsed.netloc == base_domain:
            paths.add(parsed.path)

    if not paths:
        print("⚠️ No matching URLs found for this website.")
        return

    tree = build_tree(paths)

    print("\nSite Structure:")
    print("/")
    print_tree(tree)

if __name__ == "__main__":
    main()