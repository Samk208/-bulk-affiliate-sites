"""Per-niche reference pack loader + validator.

Loads (with schema validation):
  voice.md       - YAML frontmatter + prose body
  stats.md       - YAML list of vetted statistics
  stories.md     - YAML list of first-person OR third-person attributed anecdotes
  humor.md       - YAML config (defaults + per-post-type overrides)
  forbidden.md   - plain markdown bullet list
  used-keywords.md - CSV with auto-tracked cannibalization data

Default styles root: <project>/../styles/  (workspace-level, niche-neutral)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class PackValidationError(ValueError):
    pass


VALID_FIRST_PERSON = {"allowed", "third_only", "mixed"}
VALID_GENDER_CODED = {"male", "female", "any", "none"}
VALID_HUMOR_LEVEL = {"never", "low", "warm"}

VOICE_REQUIRED = {
    "niche", "first_person", "gender_coded", "authority_voices",
    "forbidden_voices", "default_attribution_pattern",
}
HUMOR_DEFAULT_REQUIRED = {
    "level", "per_words", "in_headings", "in_safety_content", "in_medical_content",
}


@dataclass
class ReferencePack:
    niche: str
    voice: dict[str, Any]
    voice_body: str
    stats: list[dict[str, Any]] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    humor: dict[str, Any] = field(default_factory=dict)
    forbidden_text: str = ""
    used_keywords: list[dict[str, str]] = field(default_factory=list)


def load_pack(niche: str, styles_root: Path | str | None = None) -> ReferencePack:
    """Load and validate a niche's reference pack.

    Args:
        niche: niche slug (e.g. "dog-comfort")
        styles_root: override the default styles root (mostly for tests)

    Raises:
        PackValidationError: missing files or schema violations.
    """
    if styles_root is None:
        styles_root = _default_styles_root()
    styles_root = Path(styles_root)

    niche_dir = styles_root / niche
    if not niche_dir.is_dir():
        raise PackValidationError(f"niche directory not found: {niche_dir}")

    voice_yaml, voice_body = _read_frontmatter(niche_dir / "voice.md", "voice.md")
    _validate_voice(voice_yaml)

    humor = _read_yaml(niche_dir / "humor.md", "humor.md")
    _validate_humor(humor)

    stats = _read_yaml_list(niche_dir / "stats.md", "stats.md")
    stories = _read_yaml_list(niche_dir / "stories.md", "stories.md")
    _validate_stories(stories, voice_yaml)

    forbidden_path = niche_dir / "forbidden.md"
    forbidden_text = (
        forbidden_path.read_text(encoding="utf-8") if forbidden_path.exists() else ""
    )

    used_keywords = _read_used_keywords(niche_dir / "used-keywords.md")

    return ReferencePack(
        niche=niche,
        voice=voice_yaml,
        voice_body=voice_body,
        stats=stats,
        stories=stories,
        humor=humor,
        forbidden_text=forbidden_text,
        used_keywords=used_keywords,
    )


def parse_forbidden_phrases(forbidden_text: str) -> list[str]:
    """Extract bullet-list phrases from a forbidden.md file."""
    phrases: list[str] = []
    in_list = False
    for line in forbidden_text.splitlines():
        s = line.strip()
        if s.startswith("- "):
            phrase = s[2:].strip().strip('"').strip("'")
            # Skip placeholder bullets like "(none yet)"
            if phrase and not phrase.startswith("("):
                phrases.append(phrase)
            in_list = True
        elif in_list and not s:
            # blank line ends list section, but next list section may continue
            pass
    return phrases


# ---- Internals -----------------------------------------------------------

def _default_styles_root() -> Path:
    """Resolve the workspace-level styles/ directory.

    Works from both project root and git worktree (which can be deeply nested
    at .claude/worktrees/<name>/). Walks up looking for a `wordpress` ancestor
    with a `styles` sibling/child.
    """
    here = Path(__file__).resolve().parent
    # Walk up checking for wordpress/styles
    for ancestor in [here, *here.parents]:
        # Case 1: ancestor IS wordpress, styles is child
        if ancestor.name == "wordpress":
            styles = ancestor / "styles"
            if styles.exists():
                return styles
        # Case 2: ancestor's parent is wordpress, styles is parent/styles
        if ancestor.parent.name == "wordpress":
            styles = ancestor.parent / "styles"
            if styles.exists():
                return styles
    # Fallback: scripts/ -> project/ -> wordpress/ -> styles/
    return Path(__file__).resolve().parent.parent.parent / "styles"


def _read_frontmatter(path: Path, label: str) -> tuple[dict, str]:
    if not path.exists():
        raise PackValidationError(f"{label} not found at {path}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise PackValidationError(f"{label}: no YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise PackValidationError(f"{label}: malformed frontmatter")
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        raise PackValidationError(f"{label}: YAML parse error: {e}")
    if not isinstance(data, dict):
        raise PackValidationError(f"{label}: frontmatter must be a YAML mapping")
    return data, parts[2]


def _read_yaml(path: Path, label: str) -> dict:
    if not path.exists():
        raise PackValidationError(f"{label} not found at {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise PackValidationError(f"{label}: YAML parse error: {e}")
    if not isinstance(data, dict):
        raise PackValidationError(f"{label}: expected mapping")
    return data


def _read_yaml_list(path: Path, label: str) -> list:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    # Skip markdown-style comments at top of file
    yaml_lines = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("#") and not yaml_lines:
            continue
        yaml_lines.append(line)
    yaml_text = "\n".join(yaml_lines).strip()
    if not yaml_text:
        return []
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise PackValidationError(f"{label}: YAML parse error: {e}")
    if data is None:
        return []
    if not isinstance(data, list):
        raise PackValidationError(
            f"{label}: expected list, got {type(data).__name__}"
        )
    return data


def _read_used_keywords(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(text.splitlines())
    for row in reader:
        rows.append(row)
    return rows


def _validate_voice(v: dict) -> None:
    missing = VOICE_REQUIRED - set(v.keys())
    if missing:
        raise PackValidationError(
            f"voice.md missing required fields: {sorted(missing)}"
        )
    if v["first_person"] not in VALID_FIRST_PERSON:
        raise PackValidationError(
            f"voice.md first_person must be one of "
            f"{sorted(VALID_FIRST_PERSON)}, got '{v['first_person']}'"
        )
    if v["gender_coded"] not in VALID_GENDER_CODED:
        raise PackValidationError(
            f"voice.md gender_coded must be one of "
            f"{sorted(VALID_GENDER_CODED)}, got '{v['gender_coded']}'"
        )
    if not isinstance(v["authority_voices"], list):
        raise PackValidationError("voice.md authority_voices must be a list")
    if not isinstance(v["forbidden_voices"], list):
        raise PackValidationError("voice.md forbidden_voices must be a list")


def _validate_humor(h: dict) -> None:
    if "defaults" not in h:
        raise PackValidationError("humor.md missing 'defaults'")
    d = h["defaults"]
    if not isinstance(d, dict):
        raise PackValidationError("humor.md defaults must be a mapping")
    missing = HUMOR_DEFAULT_REQUIRED - set(d.keys())
    if missing:
        raise PackValidationError(
            f"humor.md defaults missing fields: {sorted(missing)}"
        )
    if d["level"] not in VALID_HUMOR_LEVEL:
        raise PackValidationError(
            f"humor.md level must be one of {sorted(VALID_HUMOR_LEVEL)}"
        )


def _validate_stories(stories: list, voice: dict) -> None:
    """Stories with attribution must match an authority voice (if voice is third_only)."""
    if voice.get("first_person") != "third_only":
        return
    authority_voices = set(voice.get("authority_voices", []))
    for i, s in enumerate(stories):
        if not isinstance(s, dict):
            raise PackValidationError(f"stories[{i}] must be a dict")
        if "attribution" not in s:
            raise PackValidationError(
                f"stories[{i}]: third_only voice mode requires "
                f"'attribution' field on every story"
            )
        if s["attribution"] not in authority_voices:
            raise PackValidationError(
                f"stories[{i}]: attribution '{s['attribution']}' not in "
                f"voice.md authority_voices {sorted(authority_voices)}"
            )
