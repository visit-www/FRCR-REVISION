import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import defaultdict

BASE_DOMAIN = "https://ajccstaging.org"
HEADERS = {"User-Agent": "StructureMapper/1.0"}

def get_internal_links(url):
    links = set()
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception:
        return links

    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/en/"):
            full = urljoin(BASE_DOMAIN, href.split("#")[0])
            links.add(full)
    return links

def build_tree(seed_urls, depth=2):
    tree = defaultdict(set)
    visited = set()

    def crawl(url, level):
        if level > depth or url in visited:
            return
        visited.add(url)

        children = get_internal_links(url)
        for child in children:
            tree[url].add(child)
            crawl(child, level + 1)

    for u in seed_urls:
        crawl(u, 1)

    return tree

def print_tree(tree, root, prefix=""):
    children = sorted(tree.get(root, []))
    for i, child in enumerate(children):
        connector = "└── " if i == len(children) - 1 else "├── "
        print(prefix + connector + child.replace(BASE_DOMAIN, ""))
        extension = "    " if i == len(children) - 1 else "│   "
        print_tree(tree, child, prefix + extension)

def main():
    with open("ajcc.json", "r") as f:
        data = json.load(f)

    seed_urls = [
        e["url"] for e in data
        if e.get("type") == "body_system"
    ]

    tree = build_tree(seed_urls, depth=2)

    print("AJCC Site Structure:")
    print("/en")
    for url in sorted(seed_urls):
        print(f"└── {url.replace(BASE_DOMAIN, '')}")
        print_tree(tree, url, "    ")

if __name__ == "__main__":
    main()