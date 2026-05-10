"""LLM rewrite step for [unverified] sentences (Phase γ).

After apply_stat_substitution flags fabricated stat claims, this step calls
an LLM to rewrite them — using verified library entries when possible, or
removing the claim. Output never invents new numbers.

Cost (per article, dog-comfort baseline):
  - ~6 flagged sentences per article batched into one call
  - input ~600 tokens, output ~300 tokens
  - Sonnet 4.6 via OpenRouter ≈ $0.0063/article
  - 105-article pilot ≈ $0.66
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


REWRITE_MODEL = "anthropic/claude-sonnet-4"
REWRITE_TIMEOUT = 90

REWRITE_SYSTEM_PROMPT = (
    "You rewrite sentences in dog-care articles that contain unverified "
    "numeric claims. Each sentence has a fabricated statistic (percentage, "
    "count, ratio, or measurement) that no real source supports.\n\n"
    "For each sentence, do ONE of:\n"
    "  (a) Use a verified statistic from the provided library if it fits.\n"
    "  (b) Make the same point with cautious non-numeric language "
    "(e.g. 'many dogs', 'some research suggests', 'often').\n"
    "  (c) Output the literal token [REMOVE] to delete the sentence.\n\n"
    "CRITICAL RULES:\n"
    "- NEVER invent new numbers. Only use numbers from the verified library.\n"
    "- Treat ALL citations in the source sentence as suspect. If the number "
    "is not literally in the verified library, paraphrase or remove it "
    "regardless of attribution. Phrases like 'AVMA notes', 'studies show', "
    "'research finds', 'According to X' do NOT make a number trustworthy — "
    "the original generator hallucinated those wrappers along with the "
    "numbers. Do not assume cited claims are real.\n"
    "- Preserve article meaning and commercial intent.\n"
    "- Match the surrounding tone (warm, helpful, conversational).\n"
    "- Keep approximately the same length so paragraph layout is preserved.\n"
    "- Drop the [unverified] marker — your output is the clean replacement.\n"
    "- Output ONLY a JSON array of strings, one rewrite per input sentence, "
    "in the same order. No preamble, no markdown fences, no commentary."
)


def find_unverified_sentences(html: str) -> list[str]:
    """Return sentences in HTML that end with a [unverified] marker.

    Walks back from each marker to the previous sentence boundary (.!?), HTML
    tag boundary (<>), or prior marker close (]). The returned strings include
    the full sentence text plus the trailing ' [unverified]' marker — the
    caller can use them directly as html.replace() targets.
    """
    results: list[str] = []
    for m in re.finditer(r'\s*\[unverified\]', html):
        marker_start = m.start()
        marker_end = m.end()
        # Find the .!? right before the marker (skip leading whitespace)
        sent_end = marker_start
        while sent_end > 0 and html[sent_end - 1] in ' \t\n':
            sent_end -= 1
        if sent_end == 0 or html[sent_end - 1] not in '.!?':
            continue
        # Walk back to find the start of THIS sentence — stop at prior
        # sentence end, HTML tag boundary, or close-bracket of prior marker.
        i = sent_end - 2
        while i >= 0:
            ch = html[i]
            if ch in '.!?<>]':
                i += 1
                break
            i -= 1
        if i < 0:
            i = 0
        while i < sent_end and html[i].isspace():
            i += 1
        sentence = html[i:marker_end].rstrip()
        if sentence:
            results.append(sentence)
    return results


def make_rewrite_messages(sentences: list[str], library: list[dict]) -> list[dict]:
    library_text = "\n".join(
        f'- "{e.get("claim","")}": {e.get("value","")} '
        f'(source: {e.get("source","?")}, {e.get("year","")})'
        for e in library
    )
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    user_msg = (
        f"Verified statistics library (the only numbers you may cite):\n"
        f"{library_text}\n\n"
        f"Sentences to rewrite (each contains [unverified]):\n"
        f"{numbered}\n\n"
        f"Return a JSON array of {len(sentences)} rewrite strings, in order."
    )
    return [
        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def _call_openrouter(messages: list[dict], model: str = REWRITE_MODEL) -> str:
    payload = {
        "model": model,
        "max_tokens": 2000,
        "messages": messages,
    }
    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REWRITE_TIMEOUT) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def parse_rewrite_response(content: str, expected_n: int) -> list[str]:
    """Parse JSON array from LLM response. Returns list of length expected_n.

    Strips markdown fences. Falls back to line-splitting if JSON parse fails.
    Pads with [REMOVE] if response is shorter; truncates if longer.
    """
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```\s*$', '', content)
    rewrites: list[str] = []
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            rewrites = [str(x).strip() for x in parsed]
    except (json.JSONDecodeError, ValueError):
        pass
    if not rewrites:
        # Fallback: split lines, strip leading "1. " / "2. " etc.
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            line = re.sub(r'^\d+\.\s*', '', line)
            line = line.strip().strip('"').strip("'").strip()
            if line:
                rewrites.append(line)
    if len(rewrites) < expected_n:
        rewrites = rewrites + ["[REMOVE]"] * (expected_n - len(rewrites))
    return rewrites[:expected_n]


def apply_llm_rewrite(
    html: str,
    library: list[dict],
    llm_call: Callable[[list[dict]], str] | None = None,
) -> tuple[str, dict]:
    """Find [unverified] sentences in HTML, rewrite via LLM, replace inline.

    If llm_call is provided (for tests), use it instead of OpenRouter.
    Returns (modified_html, report). Report keys:
      rewritten — sentences replaced with new text
      removed   — sentences replaced with empty string ([REMOVE])
      skipped   — sentences left as-is (marker stripped)
      errors    — count of LLM call failures (1 = batch failed)
    """
    sentences = find_unverified_sentences(html)
    report = {"rewritten": 0, "removed": 0, "skipped": 0, "errors": 0,
              "flagged": len(sentences)}
    if not sentences:
        return html, report

    call = llm_call or _call_openrouter
    messages = make_rewrite_messages(sentences, library)
    try:
        content = call(messages)
        rewrites = parse_rewrite_response(content, len(sentences))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            ConnectionError) as e:
        report["errors"] = 1
        report["error_msg"] = str(e)[:200]
        report["skipped"] = len(sentences)
        return html, report
    except Exception as e:  # noqa: BLE001  — defensive: never crash pipeline
        report["errors"] = 1
        report["error_msg"] = f"unexpected: {type(e).__name__}: {str(e)[:150]}"
        report["skipped"] = len(sentences)
        return html, report

    for original, new_sent in zip(sentences, rewrites):
        new_sent = new_sent.strip().strip('"').strip("'").strip()
        if not new_sent or "[REMOVE]" in new_sent.upper():
            html = html.replace(original, "", 1)
            report["removed"] += 1
        elif new_sent != original:
            # Drop any leftover [unverified] in the rewrite (shouldn't be there
            # but defensive)
            new_sent = re.sub(r'\s*\[unverified\]', '', new_sent).strip()
            html = html.replace(original, new_sent, 1)
            report["rewritten"] += 1
        else:
            # Identical output — strip the marker only
            stripped = re.sub(r'\s*\[unverified\]', '', original).strip()
            html = html.replace(original, stripped, 1)
            report["skipped"] += 1

    return html, report
