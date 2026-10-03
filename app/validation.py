"""Validation engine for BRSR data.

Runs a set of rules against every BrsrField row and returns a list of
issues. Called by /api/validation/run.
"""


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rule_required_empty(field):
    """Required field has no value."""
    if field.required and (field.value is None or str(field.value).strip() == ""):
        return {
            "severity": "High",
            "rule_name": "Mandatory field check",
            "message": f"Required field '{field.label}' is empty",
        }
    return None


def _rule_percentage_bounds(field):
    """Percentage must be between 0 and 100."""
    if field.unit != "%":
        return None
    n = _to_float(field.value)
    if n is None:
        return None
    if n < 0 or n > 100:
        return {
            "severity": "High",
            "rule_name": "Percentage bounds",
            "message": f"Percentage must be 0–100, got {field.value}",
        }
    return None


def _rule_negative_disallowed(field):
    """Emissions, energy, water cannot be negative."""
    if field.unit not in ("tCO2e", "GJ", "KL"):
        return None
    n = _to_float(field.value)
    if n is None:
        return None
    if n < 0:
        return {
            "severity": "High",
            "rule_name": "Negative value",
            "message": f"{field.unit} value cannot be negative (got {field.value})",
        }
    return None


def _rule_fatalities_threshold(field):
    """Fatalities count above 20 is unusual — verify."""
    if field.code != "P3-E5":
        return None
    n = _to_float(field.value)
    if n is not None and n > 20:
        return {
            "severity": "Medium",
            "rule_name": "Range / plausibility",
            "message": f"Fatalities count {field.value} seems unusually high — verify",
        }
    return None


def _rule_ghg_intensity(field):
    """GHG intensity above 100 tCO2e per Rs cr is high."""
    if field.code != "Core-1":
        return None
    n = _to_float(field.value)
    if n is not None and n > 100:
        return {
            "severity": "Medium",
            "rule_name": "Range / plausibility",
            "message": f"GHG intensity {field.value} tCO2e/Rs cr seems high — verify",
        }
    return None


def _rule_water_withdrawal(field):
    """Water withdrawal above 1 million KL needs verification."""
    if field.code != "P6-E2":
        return None
    n = _to_float(field.value)
    if n is not None and n > 1_000_000:
        return {
            "severity": "Low",
            "rule_name": "Unit consistency",
            "message": f"Water withdrawal {field.value} seems large — verify units (KL vs L)",
        }
    return None


def _rule_energy_large(field):
    """Renewable energy above 10M GJ needs verification."""
    if field.code != "P6-E1":
        return None
    n = _to_float(field.value)
    if n is not None and n > 10_000_000:
        return {
            "severity": "Low",
            "rule_name": "Unit consistency",
            "message": f"Energy value {field.value} seems large — verify units (GJ vs kWh)",
        }
    return None


def _rule_gender_diversity(field):
    """Gender diversity below 1% is a concern."""
    if field.code != "Core-6":
        return None
    n = _to_float(field.value)
    if n is not None and n < 1:
        return {
            "severity": "Medium",
            "rule_name": "Diversity threshold",
            "message": f"Gender diversity {field.value}% is critically low — action needed",
        }
    return None


def _rule_csr_too_large(field):
    """CSR expenditure above 1000 crore needs verification."""
    if field.code != "P8-E2":
        return None
    n = _to_float(field.value)
    if n is not None and n > 1000:
        return {
            "severity": "Low",
            "rule_name": "Range / plausibility",
            "message": f"CSR expenditure {field.value} Cr seems large — verify units",
        }
    return None


def _rule_scope3_larger_than_scope12(field, all_fields_by_entity):
    """Scope 3 is typically larger than Scope 1+2 — flag if inverted heavily."""
    if field.code != "P6-E3c":
        return None
    s3 = _to_float(field.value)
    if s3 is None:
        return None
    # Find the corresponding Scope 1 and Scope 2 for the same entity
    others = all_fields_by_entity.get(field.entity_slug, [])
    s1 = next((_to_float(f.value) for f in others if f.code == "P6-E3a"), None)
    s2 = next((_to_float(f.value) for f in others if f.code == "P6-E3b"), None)
    if s1 is None or s2 is None:
        return None
    combined = s1 + s2
    if combined > 0 and s3 < combined * 0.1:
        return {
            "severity": "Medium",
            "rule_name": "Cross-section reconciliation",
            "message": f"Scope 3 ({s3}) is much smaller than Scope 1+2 ({combined}) — verify boundary",
        }
    return None


# List of stateless rules to run on every field
RULES = [
    _rule_required_empty,
    _rule_percentage_bounds,
    _rule_negative_disallowed,
    _rule_fatalities_threshold,
    _rule_ghg_intensity,
    _rule_water_withdrawal,
    _rule_energy_large,
    _rule_gender_diversity,
    _rule_csr_too_large,
]


def run_rules(all_fields):
    """Run all rules on every field. Returns a list of issue dicts."""
    # Group fields by entity for cross-field checks
    fields_by_entity = {}
    for f in all_fields:
        fields_by_entity.setdefault(f.entity_slug, []).append(f)

    issues = []
    for f in all_fields:
        for rule in RULES:
            result = rule(f)
            if result:
                issues.append({
                    "entity_slug": f.entity_slug,
                    "section_code": f.section_code,
                    "datapoint": f.code,
                    "field_label": f.label,
                    "severity": result["severity"],
                    "rule_name": result["rule_name"],
                    "message": result["message"],
                })

        # Cross-field rule
        cross = _rule_scope3_larger_than_scope12(f, fields_by_entity)
        if cross:
            issues.append({
                "entity_slug": f.entity_slug,
                "section_code": f.section_code,
                "datapoint": f.code,
                "field_label": f.label,
                "severity": cross["severity"],
                "rule_name": cross["rule_name"],
                "message": cross["message"],
            })

    return issues


# Metadata for the UI — what rules exist
RULE_CATALOG = [
    {
        "name": "Mandatory field check",
        "desc": "All required BRSR fields must be populated before submission.",
        "severity": "High",
    },
    {
        "name": "Percentage bounds",
        "desc": "Any percentage must fall between 0 and 100.",
        "severity": "High",
    },
    {
        "name": "Negative value",
        "desc": "Emissions, energy and water values cannot be negative.",
        "severity": "High",
    },
    {
        "name": "Range / plausibility",
        "desc": "Compares values against sector benchmarks.",
        "severity": "Medium",
    },
    {
        "name": "Unit consistency",
        "desc": "Detects likely unit mismatches (kL/kL, GJ/kWh).",
        "severity": "Low",
    },
    {
        "name": "Diversity threshold",
        "desc": "Flags critically low gender diversity figures.",
        "severity": "Medium",
    },
    {
        "name": "Cross-section reconciliation",
        "desc": "Checks consistency across related sections (Scope 1+2 vs Scope 3).",
        "severity": "Medium",
    },
]