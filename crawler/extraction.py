"""HTML5 text extraction using Lexbor's native C engine through selectolax."""

from selectolax.lexbor import LexborHTMLParser


def extract_text(html: str) -> str:
    tree = LexborHTMLParser(html)
    tree.strip_tags(["head", "script", "style", "noscript", "template"], recursive=True)
    body = tree.body
    return " ".join(body.text(separator=" ", strip=True).split()) if body else ""
