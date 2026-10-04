"""AI-powered BRSR gap analysis.

Runs an automated review of all qualitative disclosures in the portal
and returns a structured report of gaps and suggestions.

Works in two modes:
  1. Rule-based (no API key required) — always available
  2. Gemini AI (if GEMINI_API_KEY is set) — richer analysis
"""

import os
import json
from typing import Any


# ---------------------------------------------------------------
# BRSR Core principles and what a good disclosure should contain
# ---------------------------------------------------------------
PRINCIPLES = {
    "P1": {
        "name": "Ethics, Transparency & Accountability",
        "keywords": ["anti-corruption", "bribery", "ethics", "whistleblower", "training", "code of conduct"],
        "expected": "Describe anti-corruption policy, whistleblower mechanism, and training coverage.",
    },
    "P3": {
        "name": "Employee Well-being & Safety",
        "keywords": ["safety", "fatalit", "injur", "LTIFR", "health insurance", "training", "welfare", "grievance"],
        "expected": "Cover safety incidents, insurance coverage, grievance mechanism, and welfare benefits.",
    },
    "P6": {
        "name": "Environment — Emissions, Energy, Water",
        "keywords": ["scope 1", "scope 2", "scope 3", "emission", "renewable", "energy", "water", "waste", "circular"],
        "expected": "Explicitly state Scope 1/2/3 categories, renewable %, water withdrawal, and waste recovery.",
    },
    "P8": {
        "name": "Inclusive Growth & Community",
        "keywords": ["csr", "community", "vulnerable", "women", "wage", "inclusive", "social impact"],
        "expected": "Describe CSR focus areas, beneficiaries, and wages to women as % of total.",
    },
    "CORE": {
        "name": "BRSR Core KPIs",
        "keywords": ["intensity", "footprint", "circularity", "diversity", "payable", "turnover"],
        "expected": "All 9 BRSR Core attributes must have evidence and methodology.",
    },
}


def _rule_based_analysis(fields: list, entity_slug: str) -> dict:
    """Fallback analysis using keyword detection — no API key needed."""
    # Collect all qualitative (textarea) values
    narratives = []
    for f in fields:
        value = getattr(f, "value", None) if not isinstance(f, dict) else f.get("value")
        field_type = getattr(f, "field_type", None) if not isinstance(f, dict) else f.get("field_type")
        label = getattr(f, "label", None) if not isinstance(f, dict) else f.get("label")
        if field_type == "textarea" and value:
            narratives.append({"label": label or "Untitled", "text": value})

    combined_text = " ".join(n["text"].lower() for n in narratives)

    gaps = []
    for code, principle in PRINCIPLES.items():
        # Check if any keyword from this principle appears anywhere
        hits = [kw for kw in principle["keywords"] if kw in combined_text]
        if not hits:
            gaps.append({
                "principle": f"{code} · {principle['name']}",
                "issue": f"No substantive disclosure found for this principle.",
                "suggestion": principle["expected"],
                "severity": "High",
            })
        elif len(hits) < 3:
            gaps.append({
                "principle": f"{code} · {principle['name']}",
                "issue": f"Only {len(hits)} of the expected keywords detected. Disclosure may be incomplete.",
                "suggestion": principle["expected"],
                "severity": "Medium",
            })

    # Extra rule — check for very short narratives
    short = [n for n in narratives if len(n["text"].split()) < 15]
    if short:
        gaps.append({
            "principle": "General",
            "issue": f"{len(short)} narratives are under 15 words, which is too brief for BRSR.",
            "suggestion": "Expand short disclosures with specifics — what, how, and measurable outcomes.",
            "severity": "Low",
        })

    if not gaps:
        summary = (
            f"Analysis of {entity_slug}: disclosures look reasonably complete. "
            f"All priority principles are covered. Review the low-severity items for polish."
        )
    else:
        high = len([g for g in gaps if g["severity"] == "High"])
        summary = (
            f"Analysis of {entity_slug}: {len(gaps)} gap(s) detected, "
            f"{high} of which are high severity. Address high-severity gaps before submission."
        )

    return {
        "mode": "rule-based",
        "entity_slug": entity_slug,
        "summary": summary,
        "gaps": gaps,
    }


# ---------------------------------------------------------------
# Optional Gemini AI mode
# ---------------------------------------------------------------
def _gemini_analysis(fields: list, entity_slug: str, api_key: str) -> dict:
    """Uses Google Gemini to generate a nuanced gap analysis."""
    try:
        import google.generativeai as genai
    except ImportError:
        return _rule_based_analysis(fields, entity_slug)

    genai.configure(api_key=api_key)

    # Build text data
    text_data = {}
    for f in fields:
        value = getattr(f, "value", None) if not isinstance(f, dict) else f.get("value")
        field_type = getattr(f, "field_type", None) if not isinstance(f, dict) else f.get("field_type")
        label = getattr(f, "label", None) if not isinstance(f, dict) else f.get("label")
        code = getattr(f, "code", None) if not isinstance(f, dict) else f.get("code")
        if field_type == "textarea" and value:
            text_data[f"{code} ({label})"] = value

    if not text_data:
        return {
            "mode": "gemini",
            "entity_slug": entity_slug,
            "summary": "No qualitative data entered yet. Nothing to analyze.",
            "gaps": [],
        }

    principles_text = "\n".join(
        f"- {k}: {v['name']} — {v['expected']}"
        for k, v in PRINCIPLES.items()
    )

    prompt = f"""You are an ESG consultant reviewing BRSR disclosures for {entity_slug}.

Disclosures entered:
{json.dumps(text_data, indent=2)}

Required principles:
{principles_text}

Identify gaps and weaknesses. Return ONLY valid JSON in this exact shape:
{{
  "summary": "one paragraph executive summary",
  "gaps": [
    {{
      "principle": "P6 · Environment",
      "issue": "specific issue found",
      "suggestion": "specific actionable fix",
      "severity": "High|Medium|Low"
    }}
  ]
}}

Focus on missing specifics (categories, scope, methodology) not grammar.
"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        parsed = json.loads(text.strip())
        parsed["mode"] = "gemini"
        parsed["entity_slug"] = entity_slug
        return parsed
    except Exception as e:
        result = _rule_based_analysis(fields, entity_slug)
        result["mode"] = f"rule-based (Gemini failed: {str(e)[:60]})"
        return result


# ---------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------
def run_gap_analysis(fields: list, entity_slug: str) -> dict:
    """Run gap analysis. Uses Gemini if API key present, else rule-based."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return _gemini_analysis(fields, entity_slug, api_key)
    return _rule_based_analysis(fields, entity_slug)