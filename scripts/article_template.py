"""
article_template.py -- Enhanced prompts with styled HTML, visual elements, copywriting.

Visual elements use inline-styled HTML divs for WordPress compatibility:
- Colored callout boxes (Pro Tips, Warnings, Key Takeaways)
- Styled expert quote blocks with attribution
- Tables with header styling and alternating rows
- Summary/TL;DR boxes
"""

import re
from datetime import datetime

from config import BANNED_WORDS
from entity_library import get_entities_for_article, get_entity_targets, NICHE_ENTITIES, ENTITY_RELATIONSHIPS

# -- Styled HTML snippets for the LLM to use in articles -------------------

VISUAL_GUIDE = """
## STYLED HTML ELEMENTS (Use these EXACT formats — they render beautifully in WordPress)

### PRO TIP BOX (use 2-3 per article):
<div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:16px 20px;margin:20px 0;border-radius:4px;">
<strong style="color:#2e7d32;">Pro Tip:</strong> Your actionable tip text here. Be specific and practical.
</div>

### WARNING BOX (use 1 per article max):
<div style="background:#fff3e0;border-left:4px solid #ff9800;padding:16px 20px;margin:20px 0;border-radius:4px;">
<strong style="color:#e65100;">Warning:</strong> Important caution the reader must know.
</div>

### KEY TAKEAWAY BOX (use 1 at start or end of major sections):
<div style="background:#e3f2fd;border-left:4px solid #2196f3;padding:16px 20px;margin:20px 0;border-radius:4px;">
<strong style="color:#1565c0;">Key Takeaway:</strong> The one thing to remember from this section.
</div>

### EXPERT QUOTE (use 1-2 per article):
<blockquote style="background:#f5f5f5;border-left:4px solid #9e9e9e;padding:16px 20px;margin:20px 0;border-radius:4px;font-style:italic;">
"The exact quote with a specific insight or data point."
<footer style="margin-top:8px;font-style:normal;color:#616161;">— <strong>Expert Name</strong>, Title/Credential, Year</footer>
</blockquote>

### STYLED TABLE (use 1-2 per article):
<table style="width:100%;border-collapse:collapse;margin:20px 0;">
<thead>
<tr style="background:#1a237e;color:white;">
<th style="padding:12px 16px;text-align:left;">Column 1</th>
<th style="padding:12px 16px;text-align:left;">Column 2</th>
<th style="padding:12px 16px;text-align:left;">Column 3</th>
</tr>
</thead>
<tbody>
<tr style="background:#f5f5f5;">
<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td>
<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td>
<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td>
</tr>
<tr>
<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td>
<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td>
<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td>
</tr>
</tbody>
</table>

### TL;DR / QUICK ANSWER BOX (use at very top of article):
<div style="background:#f3e5f5;border:2px solid #9c27b0;padding:20px;margin:0 0 24px 0;border-radius:8px;">
<strong style="color:#6a1b9a;font-size:1.1em;">Quick Answer:</strong>
<ul style="margin:10px 0 0 0;padding-left:20px;line-height:1.8;">
<li>First key point — the direct answer to the search query</li>
<li>Second key point — the most important detail or number</li>
<li>Third key point — what to do next or avoid</li>
</ul>
</div>
"""

# -- System prompt --------------------------------------------------------

SYSTEM_PROMPT = """You are an expert writer who creates visually rich, engaging affiliate blog articles. Your content reads like it was written by a passionate expert who genuinely tested products and wants to help.

## WRITING STYLE
1. **Conversational and direct.** Write like you're explaining to a friend. Use "you" and "I" naturally.
2. **Hook the reader fast.** First sentence must answer the search query or make a bold claim with data.
3. **SKINNY PARAGRAPHS (CRITICAL).** Maximum 2-3 sentences per paragraph. HARD LIMIT: 50 words per paragraph. Break longer paragraphs into two. One-sentence paragraphs are encouraged. White space is your friend on mobile. This is the #1 readability factor.
4. **Vary sentence rhythm.** Mix punchy 5-word sentences with 15-word ones. Never monotone.
5. **Use contractions.** Don't, it's, we've, you'll, that's — write like you speak.
6. **Specific over vague.** "4 inches of CertiPUR-US certified memory foam" beats "quality materials."
7. **Show, don't tell.** "My arthritic Lab went from limping to sprinting in 3 weeks" beats "this product helps dogs."

## COPYWRITING TECHNIQUES (use throughout)
- **Open loops:** "There's one mistake 90% of owners make — I'll cover it in the next section."
- **Pattern interrupts:** Short. Like this. Then a longer sentence to change the pace.
- **Bucket brigades:** "Here's the thing:", "But wait —", "Now here's where it gets interesting:", "The bottom line?"
- **Power words:** Proven, tested, instant, essential, mistake, secret, surprisingly, warning
- **Emotional triggers:** frustration ("tired of replacing beds every 3 months?"), relief ("finally, a solution"), fear of missing out ("most owners don't realize...")

## VISUAL ELEMENTS (MANDATORY)
{visual_guide}

## GEO OPTIMIZATION (for AI search engines)
1. Start with a Quick Answer box (TL;DR) as bullet list — this is what ChatGPT/Perplexity will cite
2. **H2s MUST be question-form.** Every H2 heading is a question a reader would type into Google. At least 6 of 8 H2s must end with a question mark.
   - GOOD H2: "How do I measure my dog for a bed?" / "What size bed does a 60-pound dog need?" / "Should the bed be bigger than my dog?"
   - BAD H2: "Measuring Your Dog" / "Sizing Guide" / "Large Dog Considerations" — these are section labels, not questions.
3. **H3s MUST also be question-form** where they appear under an H2. Example: "Why do large dogs need more joint support?"
4. **Answer each H2 and H3 in the FIRST sentence.** Direct, bolded answer, then expand in the paragraphs below.
5. Include 1+ statistic with source per H2 section.
6. Use "as of {current_year}" for temporal data.

## E-E-A-T SIGNALS (MANDATORY)
- **Experience:** "After testing 12 orthopedic beds over 6 months..." / "My vet recommended..."
- **Expertise:** Cite specific measurements, temperatures, ingredients, percentages
- **Authority:** Expert quotes using the styled blockquote format above
- **Trust:** Mention downsides honestly. "The one thing I didn't love..."

## OUTPUT FORMAT
- Return clean HTML — no <html>, <head>, <body>, or markdown
- Use <h2> for main sections (MUST be question-form, end with ?), <h3> for subsections (also question-form)
- Both H2 and H3 must be answered in the FIRST sentence beneath them
- Do NOT include <h1>
- No <h4>, <h5>, <h6>
- Use the styled div/blockquote/table formats shown above for visual elements
- Internal links: <a href="/SLUG/">ANCHOR TEXT</a>
- End with: <p><em>Last updated: {current_date}</em></p>

## DIFFERENTIATION (CRITICAL — this is what separates content that ranks from content that gets ignored)
1. **Do NOT just repeat what top results say.** If the SERP research shows all competitors cover the same 5 subtopics, cover those (they are mandatory) BUT also cover 2-3 things they miss.
2. **Add a genuine perspective or counter-narrative.** "Most guides recommend X — but after testing, I found Y works better because..."
3. **Include at least one original comparison, calculation, or data synthesis** that doesn't exist in any single competitor article.
4. **Address the CONTENT GAPS identified in the SERP research.** These gaps are your competitive advantage.
5. **Use the CONTENT ANGLE from the SERP research** — if an angle is underserved, use it.

## BANNED (NEVER USE)
Words: {banned_words}
Intros: "In today's", "When it comes to", "If you're looking for", "Are you tired of", "In this article"
""".format(
    visual_guide=VISUAL_GUIDE,
    banned_words=", ".join(BANNED_WORDS),
    current_year=datetime.now().year,
    current_date=datetime.now().strftime("%B %d, %Y"),
)


def _build_entity_block(niche_slug: str, keyword: str = "") -> str:
    """Build structured entity guidance for the LLM prompt.

    When keyword is provided, returns article-specific primary/secondary entities
    with relationships. Otherwise falls back to full niche entity list.
    """
    entities = NICHE_ENTITIES.get(niche_slug, {})
    if not entities:
        return ""

    # Keyword-specific targeting
    targets = get_entity_targets(niche_slug, keyword) if keyword else None

    if targets and targets["primary"]:
        primary_lines = []
        for p in targets["primary"]:
            primary_lines.append(f"- {p['name']} ({p['type']}) -- mention 2+ times, use in at least 1 H2 heading")
        secondary_lines = [f"- {s['name']} ({s['type']})" for s in targets["secondary"]]

        # Format relationships as natural language
        rel_lines = []
        for subj, verb, obj in targets["relationships"][:6]:
            rel_lines.append(f'- "{subj} {verb} {obj}"')

        block = f"""
ENTITY REQUIREMENTS (these signal topical authority to Google -- use specific names, NEVER generic terms):

PRIMARY ENTITIES (MUST appear in H2 headings AND body text -- mention each 2+ times):
{chr(10).join(primary_lines)}

SECONDARY ENTITIES (use where relevant in body paragraphs):
{chr(10).join(secondary_lines) if secondary_lines else "- (use any niche entities that fit naturally)"}"""

        if rel_lines:
            block += f"""

ENTITY RELATIONSHIPS (connect these naturally in your writing):
{chr(10).join(rel_lines)}"""

        block += """

RULES: Use exact entity names -- "memory foam" not "quality materials", "American Kennel Club" not "pet organizations". Place primary entities in the introduction and at least one H2 heading."""
        return block

    # Fallback: full niche list (backward compatible)
    entity_lines = [f"- {name} ({meta['@type']})" for name, meta in entities.items()]
    return f"""
ENTITY REQUIREMENTS (these signal topical authority -- use specific names, NEVER generic terms):
{chr(10).join(entity_lines)}

RULES: Mention at least 6 of these entities in your article. Place the 3 most relevant in H2 subheadings.
Use exact entity names -- "memory foam" not "quality materials"."""


def build_howto_prompt(
    title: str,
    outline_focus: str,
    slug: str,
    niche_name: str,
    related_links: list[dict],
    product_context: str = "",
    serp_context: str = "",
    niche_slug: str = "",
) -> str:
    links_block = "\n".join(
        f"- /{link['slug']}/ -- {link['title']}"
        for link in related_links
    ) if related_links else "- (no related roundups)"

    current_date = datetime.now().strftime("%B %d, %Y")

    serp_block = ""
    if serp_context:
        serp_block = f"""
SERP RESEARCH (from top-ranking articles — use these real facts, data points, and subtopics):
{serp_context}

IMPORTANT:
- Use the specific data, products, and statistics from the research above — real sources beat fabricated numbers.
- Match the SEARCH INTENT and CONTENT FORMAT identified in the research.
- Cover ALL the KEY SUBTOPICS (these are mandatory for ranking).
- Exploit the CONTENT GAPS — this is where you differentiate and provide information gain.
- Use the recommended CONTENT ANGLE if one is identified."""

    entity_block = _build_entity_block(niche_slug, keyword=title) if niche_slug else ""

    return f"""Write a How-To Guide article with rich visual styling.

TITLE: {title}
TARGET READER: {outline_focus}
NICHE: {niche_name}
URL SLUG: /{slug}/

INTERNAL LINKS (weave naturally + list in "Related Reading"):
{links_block}
{serp_block}
{entity_block}
{f"NICHE CONTEXT:{chr(10)}{product_context[:1000]}" if product_context else ""}

STRUCTURE:

1. **Quick Answer Box** (TL;DR div at top)
   - 3-4 bullet points using the styled <ul> format — direct, scannable answer

2. **Introduction** (100-150 words)
   - Hook with a surprising stat or bold claim
   - Who this guide is for + what they'll learn
   - Open loop: hint at a common mistake you'll cover later

3. **Quick Reference Table** (styled table)
   - Steps, time needed, materials, estimated cost

4. **Step-by-Step Sections** (3-5 H2s, 200-300 words each)
   - Question-based H3 subheadings
   - Pro Tip boxes in at least 2 sections
   - Specific measurements, temperatures, product names
   - Weave in internal links naturally
   - Use bucket brigades between sections

5. **Common Mistakes** (H2)
   - 4-5 mistakes — use a Warning box for the worst one
   - "I made this mistake myself — here's what happened..."

6. **Expert Insight** (H2)
   - 1-2 expert blockquotes with styled format
   - Key Takeaway box summarizing the expert advice

7. **FAQ** (H2, 4-5 questions as H3s)
   - Answer in first sentence, elaborate briefly

8. **Related Reading** (H2)
   - Internal links as a styled list

9. End: <p><em>Last updated: {current_date}</em></p>

TARGET: 1,800-2,500 words. Make it visually rich — callout boxes, styled tables, expert quotes."""


def build_tips_prompt(
    title: str,
    outline_focus: str,
    slug: str,
    niche_name: str,
    related_links: list[dict],
    product_context: str = "",
    serp_context: str = "",
    niche_slug: str = "",
) -> str:
    links_block = "\n".join(
        f"- /{link['slug']}/ -- {link['title']}"
        for link in related_links
    ) if related_links else "- (no related roundups)"

    current_date = datetime.now().strftime("%B %d, %Y")

    serp_block = ""
    if serp_context:
        serp_block = f"""
SERP RESEARCH (from top-ranking articles — use these real facts, data points, and subtopics):
{serp_context}

IMPORTANT:
- Use the specific data, products, and statistics from the research above — real sources beat fabricated numbers.
- Match the SEARCH INTENT and CONTENT FORMAT identified in the research.
- Cover ALL the KEY SUBTOPICS (these are mandatory for ranking).
- Exploit the CONTENT GAPS — this is where you differentiate and provide information gain.
- Use the recommended CONTENT ANGLE if one is identified."""

    entity_block = _build_entity_block(niche_slug, keyword=title) if niche_slug else ""

    return f"""Write a Tips & Care article with rich visual styling.

TITLE: {title}
TARGET READER: {outline_focus}
NICHE: {niche_name}
URL SLUG: /{slug}/

INTERNAL LINKS (weave naturally + list in "Related Reading"):
{links_block}
{serp_block}
{entity_block}
{f"NICHE CONTEXT:{chr(10)}{product_context[:1000]}" if product_context else ""}

STRUCTURE:

1. **Quick Answer Box** (TL;DR div at top)
   - 3-4 bullet points using the styled <ul> format — direct, scannable answer

2. **Introduction** (100-150 words)
   - Lead with empathy or a relatable scenario
   - "Your dog does X and you're wondering why..."
   - Include a stat about how common this issue is

3. **Key Facts Table** (styled table)
   - Causes, symptoms, solutions, or key data at a glance

4. **Main Sections** (4-6 H2s, 200-300 words each)
   - Question-based H3s ("Why does my dog...?")
   - Pro Tip boxes for actionable advice
   - Key Takeaway boxes for important points
   - Real-world examples and scenarios
   - Link to product roundups where relevant

5. **When to See a Professional** (H2)
   - Warning box for serious signs
   - Clear thresholds/criteria

6. **Expert Perspective** (H2)
   - Styled expert blockquote
   - Evidence-based recommendation

7. **FAQ** (H2, 4-5 questions as H3s)

8. **Related Reading** (H2)

9. End: <p><em>Last updated: {current_date}</em></p>

TARGET: 1,500-2,000 words. Visually engaging — styled callouts, tables, expert quotes throughout."""


def build_comparison_prompt(
    title: str,
    outline_focus: str,
    slug: str,
    niche_name: str,
    related_links: list[dict],
    product_context: str = "",
    serp_context: str = "",
    niche_slug: str = "",
) -> str:
    """Template for commercial-intent comparison/roundup articles."""
    links_block = "\n".join(
        f"- /{link['slug']}/ -- {link['title']}"
        for link in related_links
    ) if related_links else "- (no related articles)"

    current_date = datetime.now().strftime("%B %d, %Y")

    serp_block = ""
    if serp_context:
        serp_block = f"""
SERP RESEARCH (from top-ranking articles — use these real facts, data points, and subtopics):
{serp_context}

IMPORTANT:
- Use the specific data, products, and statistics from the research above — real sources beat fabricated numbers.
- Match the SEARCH INTENT and CONTENT FORMAT identified in the research.
- Cover ALL the KEY SUBTOPICS (these are mandatory for ranking).
- Exploit the CONTENT GAPS — this is where you differentiate and provide information gain.
- Use the recommended CONTENT ANGLE if one is identified."""

    entity_block = _build_entity_block(niche_slug, keyword=title) if niche_slug else ""

    return f"""Write a Product Comparison / Roundup article with rich visual styling.

TITLE: {title}
TARGET READER: {outline_focus}
NICHE: {niche_name}
URL SLUG: /{slug}/

INTERNAL LINKS (weave naturally + list in "Related Reading"):
{links_block}
{serp_block}
{entity_block}
{f"NICHE CONTEXT:{chr(10)}{product_context[:1000]}" if product_context else ""}

STRUCTURE:

1. **Quick Answer Box** (TL;DR div at top)
   - Name the #1 pick upfront with 1-sentence why
   - 2-3 runner-ups for specific use cases ("best budget", "best for X")

2. **Introduction** (100-150 words)
   - Hook with a frustration or common buying mistake
   - "I tested/researched X products over Y weeks/months..."
   - State your evaluation criteria upfront

3. **Quick Comparison Table** (styled table)
   - Product name | Best For | Key Spec | Price Range | Our Verdict
   - 4-8 products max

4. **Individual Product Sections** (4-8 H2s, 150-250 words each)
   - H2: Product Name — Best for [Use Case]
   - Pros (3-4 bullet points with specific details)
   - Cons (1-2 honest downsides)
   - Key specs or measurements
   - "Who this is for" one-liner
   - Pro Tip or Warning box where relevant

5. **How We Evaluated** (H2)
   - Your testing methodology or research criteria
   - "I prioritized X, Y, Z because..."
   - This is your E-E-A-T experience signal

6. **Buyer's Guide** (H2)
   - 3-4 H3 questions: "What to look for in...", "How much should you spend on..."
   - Key Takeaway box with decision framework

7. **FAQ** (H2, 4-5 questions as H3s)

8. **Related Reading** (H2)

9. End: <p><em>Last updated: {current_date}</em></p>

TARGET: 2,000-3,000 words. This is commercial intent — readers want to make a buying decision. Be specific about products, prices, and tradeoffs. Honesty about downsides builds trust."""


def build_buyers_guide_prompt(
    title: str,
    outline_focus: str,
    slug: str,
    niche_name: str,
    related_links: list[dict],
    product_context: str = "",
    serp_context: str = "",
    niche_slug: str = "",
) -> str:
    """Template for transactional-intent buying guide articles."""
    links_block = "\n".join(
        f"- /{link['slug']}/ -- {link['title']}"
        for link in related_links
    ) if related_links else "- (no related articles)"

    current_date = datetime.now().strftime("%B %d, %Y")

    serp_block = ""
    if serp_context:
        serp_block = f"""
SERP RESEARCH (from top-ranking articles — use these real facts, data points, and subtopics):
{serp_context}

IMPORTANT:
- Use the specific data, products, and statistics from the research above — real sources beat fabricated numbers.
- Match the SEARCH INTENT and CONTENT FORMAT identified in the research.
- Cover ALL the KEY SUBTOPICS (these are mandatory for ranking).
- Exploit the CONTENT GAPS — this is where you differentiate and provide information gain.
- Use the recommended CONTENT ANGLE if one is identified."""

    entity_block = _build_entity_block(niche_slug, keyword=title) if niche_slug else ""

    return f"""Write a Buying Guide article with rich visual styling.

TITLE: {title}
TARGET READER: {outline_focus}
NICHE: {niche_name}
URL SLUG: /{slug}/

INTERNAL LINKS (weave naturally + list in "Related Reading"):
{links_block}
{serp_block}
{entity_block}
{f"NICHE CONTEXT:{chr(10)}{product_context[:1000]}" if product_context else ""}

STRUCTURE:

1. **Quick Answer Box** (TL;DR div at top)
   - 3-4 bullet points: what to prioritize, price range to expect, biggest mistake to avoid

2. **Introduction** (100-150 words)
   - Acknowledge the overwhelm: "There are 50+ options and most guides just list specs..."
   - Your angle: experience-based, research-backed decision framework
   - "After researching X options, here's what actually matters..."

3. **Decision Framework Table** (styled table)
   - Need | Recommended Type | Budget | Key Feature
   - Help readers self-select before deep-diving

4. **What to Look For** (H2, 3-5 H3 subsections)
   - Each H3 covers one buying criterion
   - Specific numbers: "Look for at least X inches of Y" not "look for good quality"
   - Pro Tip boxes with insider knowledge
   - Warning box for common traps (marketing gimmicks, unnecessary features)

5. **What to Avoid** (H2)
   - 3-4 specific mistakes with real consequences
   - "I see this mistake constantly — people buy X when they actually need Y..."

6. **Budget Guide** (H2)
   - Price tiers with what you get at each level
   - "Under $X: expect... | $X-$Y: sweet spot | Over $Y: diminishing returns"
   - Key Takeaway: best value recommendation

7. **Expert Perspective** (H2)
   - Styled expert blockquote
   - Evidence-based recommendation

8. **FAQ** (H2, 4-5 questions as H3s)

9. **Related Reading** (H2)

10. End: <p><em>Last updated: {current_date}</em></p>

TARGET: 1,800-2,500 words. This reader is ready to buy — help them make the RIGHT decision, not just any decision. Be opinionated and specific."""


def build_prompt(
    title: str,
    outline_focus: str,
    slug: str,
    category: str,
    niche_name: str,
    related_links: list[dict],
    product_context: str = "",
    serp_context: str = "",
    niche_slug: str = "",
) -> str:
    if category == "How-To Guides":
        return build_howto_prompt(
            title, outline_focus, slug, niche_name, related_links, product_context, serp_context, niche_slug
        )
    elif category in ("Best Products", "Comparisons", "Reviews"):
        return build_comparison_prompt(
            title, outline_focus, slug, niche_name, related_links, product_context, serp_context, niche_slug
        )
    elif category == "Buying Guides":
        return build_buyers_guide_prompt(
            title, outline_focus, slug, niche_name, related_links, product_context, serp_context, niche_slug
        )
    else:
        return build_tips_prompt(
            title, outline_focus, slug, niche_name, related_links, product_context, serp_context, niche_slug
        )


def build_schema(
    title: str,
    slug: str,
    category: str,
    description: str,
    html_content: str,
    niche_name: str,
    niche_slug: str = "",
    site_url: str = "",
) -> list | dict:
    """Generate JSON-LD schema with entity enrichment.

    Args:
        site_url: Optional site base URL (e.g. "https://dogcomfort.example.com").
            If provided, `mainEntityOfPage.@id` becomes `{site_url}/{slug}/`.
            If omitted, a relative `/{slug}/` @id is used (resolves against
            the rendered page URL at import time).
    """
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Build article URL for mainEntityOfPage (WebPage, per Schema.org spec)
    article_url = f"{site_url.rstrip('/')}/{slug}/" if site_url else f"/{slug}/"

    # @type first per Schema.org convention; overwritten below for HowTo
    base_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "mainEntityOfPage": {"@type": "WebPage", "@id": article_url},
        "author": {"@type": "Person", "name": "Sam Konneh"},
        "publisher": {"@type": "Organization", "name": niche_name},
        "datePublished": current_date,
        "dateModified": current_date,
    }

    if niche_slug:
        entity_data = get_entities_for_article(niche_slug, html_content)
        if entity_data["about"]:
            base_schema["about"] = []
            for e in entity_data["about"]:
                entry = {"@type": e["@type"], "name": e["name"]}
                same_as = [e["sameAs"]] if e.get("sameAs") else []
                if e.get("wikidata"):
                    same_as.append(e["wikidata"])
                entry["sameAs"] = same_as if len(same_as) > 1 else (same_as[0] if same_as else "")
                base_schema["about"].append(entry)
        if entity_data["mentions"]:
            base_schema["mentions"] = []
            for e in entity_data["mentions"]:
                entry = {"@type": e["@type"], "name": e["name"]}
                same_as = [e["sameAs"]] if e.get("sameAs") else []
                if e.get("wikidata"):
                    same_as.append(e["wikidata"])
                entry["sameAs"] = same_as if len(same_as) > 1 else (same_as[0] if same_as else "")
                base_schema["mentions"].append(entry)

    if category == "How-To Guides":
        steps = []
        h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html_content)
        skip = {"frequently asked questions", "related reading", "related articles",
                "common mistakes", "expert insight", "expert perspective",
                "what you'll need", "quick reference"}
        for heading in h2_matches:
            clean = re.sub(r'<[^>]+>', '', heading).strip()
            if clean.lower() not in skip:
                steps.append({"@type": "HowToStep", "position": len(steps) + 1, "name": clean})
        # Override @type (set to "Article" by default at construction)
        base_schema["@type"] = "HowTo"
        base_schema["name"] = title
        base_schema["description"] = description[:160]
        base_schema["step"] = steps if steps else [{"@type": "HowToStep", "position": 1, "name": title}]
    else:
        base_schema["headline"] = title
        base_schema["description"] = description[:160]

    schemas = [base_schema]

    faq_section = re.search(
        r'<h2[^>]*>.*?(?:FAQ|[Ff]requently\s+[Aa]sked).*?</h2>(.*?)(?=<h2|$)',
        html_content, re.DOTALL,
    )
    if faq_section:
        questions = re.findall(r'<h3[^>]*>(.*?)</h3>\s*<p>(.*?)</p>', faq_section.group(1), re.DOTALL)
        if questions:
            schemas.append({
                "@context": "https://schema.org", "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": re.sub(r'<[^>]+>', '', q).strip(),
                     "acceptedAnswer": {"@type": "Answer", "text": re.sub(r'<[^>]+>', '', a).strip()}}
                    for q, a in questions[:5]
                ],
            })

    return schemas if len(schemas) > 1 else schemas[0]
