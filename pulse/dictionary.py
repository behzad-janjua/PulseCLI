from __future__ import annotations

import difflib
import re
from pathlib import Path

import yaml

DICT_PATH = (
    Path.home() / "Library" / "Application Support" / "Pulse" / "dictionary.yaml"
)


def _load_raw() -> dict[str, str]:
    if not DICT_PATH.exists():
        return {}
    try:
        with DICT_PATH.open() as f:
            data = yaml.safe_load(f) or {}
        corrections = data.get("corrections", {}) if isinstance(data, dict) else {}
        return {str(k): str(v) for k, v in corrections.items()}
    except Exception:
        return {}


def _save_raw(corrections: dict[str, str]) -> None:
    DICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DICT_PATH.open("w") as f:
        yaml.dump({"corrections": corrections}, f, default_flow_style=False)


def apply_dictionary(text: str) -> str:
    corrections = _load_raw()
    if not corrections:
        return text
    # Longest spoken phrase first to avoid partial clobbers.
    ordered = sorted(corrections.items(), key=lambda kv: len(kv[0]), reverse=True)
    result = text
    for spoken, replacement in ordered:
        escaped = re.escape(spoken)
        prefix = r'\b' if spoken and re.match(r'\w', spoken[0]) else ''
        suffix = r'\b' if spoken and re.match(r'\w', spoken[-1]) else ''
        result = re.sub(prefix + escaped + suffix, lambda _: replacement, result, flags=re.IGNORECASE)
    return result


def add_correction(spoken: str, replacement: str) -> None:
    corrections = _load_raw()
    corrections[spoken.lower().strip()] = replacement.strip()
    _save_raw(corrections)


def infer_corrections(original: str, corrected: str) -> list[tuple[str, str]]:
    """Diff *original* and *corrected* word-by-word and return (spoken, replacement) pairs.

    Falls back to a single whole-phrase pair when the diff produces nothing actionable.
    """
    orig_words = original.lower().split()
    corr_words = corrected.split()
    corr_lower = [w.lower() for w in corr_words]

    matcher = difflib.SequenceMatcher(None, orig_words, corr_lower, autojunk=False)
    pairs: list[tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            spoken = " ".join(orig_words[i1:i2])
            replacement = " ".join(corr_words[j1:j2])
            if spoken and replacement:
                pairs.append((spoken, replacement))

    if not pairs and original.lower().strip() != corrected.lower().strip():
        # No clear diff — save the whole original utterance as a phrase correction.
        pairs.append((original.lower().strip(), corrected.strip()))

    return pairs
