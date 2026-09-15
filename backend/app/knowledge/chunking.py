"""Markdown/MDX chunking adapted from CyberTron Agentic Stack kb_chunk.py."""
from pathlib import Path
import hashlib
import json
import re

MIN_CHARS = 250
TARGET_CHARS = 900
MAX_CHARS = 1800

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "section"


def sanitize_markdown(text: str) -> str:
    """Remove presentation-only Markdown/MDX metadata before chunking."""

    # Strip YAML front matter at the beginning of the document.
    text = re.sub(
        r"\A---\s*\n.*?\n---\s*\n",
        "",
        text,
        flags=re.DOTALL,
    )

    # Strip ES module import/export lines commonly used by MDX/Docusaurus.
    text = re.sub(
        r"^(?:import|export)\s+.*?;\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Remove Head blocks, including SEO/schema JSON that is presentation
    # metadata rather than reference documentation.
    text = re.sub(
        r"<Head\b[^>]*>.*?</Head>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove standalone JSX component tags while leaving ordinary Markdown
    # and code examples intact.
    text = re.sub(
        r"^\s*</?[A-Z][A-Za-z0-9_.:-]*(?:\s+[^>]*)?/?>\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Collapse excessive blank lines produced by removals.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n"


def split_markdown_sections(text: str):
    sections = []
    heading = "Document"
    buffer = []

    def flush():
        nonlocal buffer
        body = "\n".join(buffer).strip()
        if body:
            sections.append((heading, body))
        buffer = []

    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            flush()
            heading = re.sub(r"^#{1,6}\s+", "", line).strip()
        else:
            buffer.append(line)

    flush()
    return sections


def split_large_text(text: str, max_chars: int = MAX_CHARS):
    if len(text) <= max_chars:
        return [text]

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        candidate = (
            paragraph
            if not current
            else current + "\n\n" + paragraph
        )

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            for i in range(0, len(paragraph), max_chars):
                piece = paragraph[i:i + max_chars].strip()
                if piece:
                    chunks.append(piece)

    if current:
        chunks.append(current)

    return chunks


def normalize_sections(sections):
    combined = []
    pending_heading = None
    pending_body = ""

    for heading, body in sections:
        block = body.strip()

        if not pending_body:
            pending_heading = heading
            pending_body = block
        else:
            candidate = pending_body + "\n\n" + block

            if (
                len(pending_body) < MIN_CHARS
                and len(candidate) <= TARGET_CHARS
            ):
                pending_heading = (
                    f"{pending_heading} / {heading}"
                )
                pending_body = candidate
            else:
                combined.append(
                    (pending_heading, pending_body)
                )
                pending_heading = heading
                pending_body = block

    if pending_body:
        combined.append(
            (pending_heading, pending_body)
        )

    final = []

    for heading, body in combined:
        parts = split_large_text(body)

        if len(parts) == 1:
            final.append((heading, parts[0]))
        else:
            for i, part in enumerate(parts, start=1):
                final.append(
                    (f"{heading} — Part {i}", part)
                )

    return final


def chunk_document(
    kb_id: str,
    path: Path,
    source_root: Path,
    output_root: Path,
):
    rel = path.relative_to(source_root)
    text = path.read_text(
        encoding="utf-8",
    )

    text = sanitize_markdown(text)
    sections = split_markdown_sections(text)
    sections = normalize_sections(sections)

    records = []

    for index, (heading, body) in enumerate(
        sections,
        start=1,
    ):
        content = f"# {heading}\n\n{body}".strip()

        digest = hashlib.sha256(
            (
                rel.as_posix()
                + "\n"
                + heading
                + "\n"
                + content
            ).encode("utf-8")
        ).hexdigest()

        chunk_id = (
            f"{slugify(path.stem)}-"
            f"{index:03d}-"
            f"{digest[:12]}"
        )

        record = {
            "chunk_id": chunk_id,
            "kb": kb_id,
            "source_path": rel.as_posix(),
            "source_title": path.stem,
            "section": heading,
            "sha256": digest,
            "content": content,
        }

        outfile = output_root / f"{chunk_id}.json"

        outfile.write_text(
            json.dumps(record, indent=2) + "\n",
            encoding="utf-8",
        )

        records.append(record)

    return records



