"""Minimal YAML front matter parsing (Jekyll-style)."""
import yaml

DELIM = "---"


def parse_front_matter(text: str):
    """Split `text` into (front_matter_dict, body_str).

    If no valid front matter block is found, returns ({}, text) unchanged.
    """
    if not text.startswith(DELIM):
        return {}, text

    lines = text.split("\n")
    if lines[0].strip() != DELIM:
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == DELIM:
            end_idx = i
            break

    if end_idx is None:
        # Opened but never closed - treat as no front matter.
        return {}, text

    fm_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    fm = yaml.safe_load(fm_text) or {}
    if not isinstance(fm, dict):
        fm = {}

    return fm, body
