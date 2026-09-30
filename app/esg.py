"""ESG / SDG aggregation helpers — maps BRSR section codes to NGRBC principles."""

# Map BRSR section code (as seeded in DB) → NGRBC principle ID
# Adjust the left-hand keys if your seed uses different codes.
SECTION_TO_PRINCIPLE = {
    "A": "P1",
    "B": "P1",
    "C": "P2",
    "D": "P3",
    "E": "P4",
    "F": "P5",
    "G": "P6",
    "H": "P7",
    "I": "P8",
    "J": "P9",
}

# Numeric indicators we extract per principle.
# Keys are the BrsrField.code values you'd find in the DB.
# Adjust to match the codes you seeded.
FIELD_TO_KEY = {
    "P6_S1": "scope1",
    "P6_S2": "scope2",
    "P6_EN": "energyConsumption",
    "P6_WA": "waterWithdrawal",
    "P6_WR": "wasteRecycled",
    "P3_LT": "ltifr",
    "P3_TR": "trainingHours",
    "P3_WW": "womenWorkforce",
    "P3_SI": "safetyIncidents",
    "P1_ET": "ethicsTraining",
    "P1_AC": "antiCorruptionCases",
    "P1_PC": "policyCoverage",
    "P4_GR": "grievancesReceived",
    "P4_RS": "grievancesResolved",
    "P4_CM": "communityMeetings",
    "P5_HT": "hrTraining",
    "P5_HC": "hrComplaints",
    "P5_MW": "minimumWage",
    "P8_CS": "csrSpend",
    "P8_LE": "localEmployment",
    "P8_SC": "scstEmployment",
    "P9_PS": "productSafety",
    "P9_CC": "customerComplaints",
    "P9_CR": "complaintsResolved",
    "P2_RI": "recycledInput",
    "P2_PSI": "productSafetyIncidents",
    "P2_LC": "lifecycleAssessments",
    "P7_PP": "policyPositions",
    "P7_TA": "tradeAssociations",
}


def empty_principle_data():
    return {
        "P1": {"ethicsTraining": 0, "antiCorruptionCases": 0, "policyCoverage": 0},
        "P2": {"recycledInput": 0, "productSafetyIncidents": 0, "lifecycleAssessments": 0},
        "P3": {"ltifr": 0, "trainingHours": 0, "womenWorkforce": 0, "safetyIncidents": 0},
        "P4": {"grievancesReceived": 0, "grievancesResolved": 0, "communityMeetings": 0},
        "P5": {"hrTraining": 0, "hrComplaints": 0, "minimumWage": 0},
        "P6": {
            "scope1": 0,
            "scope2": 0,
            "energyConsumption": 0,
            "waterWithdrawal": 0,
            "wasteRecycled": 0,
        },
        "P7": {"policyPositions": 0, "tradeAssociations": 0},
        "P8": {"csrSpend": 0, "localEmployment": 0, "scstEmployment": 0},
        "P9": {"productSafety": 0, "customerComplaints": 0, "complaintsResolved": 0},
    }


def aggregate_fields_to_principles(fields):
    """fields: list of BrsrField rows. Returns principle-keyed dict."""
    out = empty_principle_data()
    for f in fields:
        p_id = SECTION_TO_PRINCIPLE.get(f.section_code)
        if not p_id:
            continue
        key = FIELD_TO_KEY.get(f.code)
        if not key:
            continue
        try:
            val = float(f.value) if f.value not in (None, "") else 0
        except (ValueError, TypeError):
            val = 0
        out[p_id][key] += val
    return out


def compute_principle_scores(agg):
    """Average normalized 0-100 score per principle."""
    maxes = {
        "P1": [100, 20, 100],
        "P2": [100, 20, 30],
        "P3": [2, 80, 100, 100],
        "P4": [500, 500, 100],
        "P5": [100, 20, 100],
        "P6": [500000, 200000, 10000, 50, 100],
        "P7": [20, 30],
        "P8": [500, 100, 100],
        "P9": [100, 500, 100],
    }
    scores = {}
    for pid, vals in agg.items():
        keys = list(vals.keys())
        maxs = maxes.get(pid, [100] * len(keys))
        total = 0
        for i, k in enumerate(keys):
            m = maxs[i] if i < len(maxs) else 100
            total += min(100, (vals[k] / m) * 100) if m else 0
        scores[pid] = round(total / len(keys)) if keys else 0
    return scores


PRINCIPLE_SDGS = {
    "P1": [16],
    "P2": [12],
    "P3": [3, 8],
    "P4": [17],
    "P5": [5, 8, 10],
    "P6": [6, 7, 12, 13, 14, 15],
    "P7": [16, 17],
    "P8": [1, 8, 10, 11],
    "P9": [3, 12],
}


def compute_sdg_scores(principle_scores):
    sdg = {}
    for pid, score in principle_scores.items():
        for s_id in PRINCIPLE_SDGS.get(pid, []):
            sdg[s_id] = max(sdg.get(s_id, 0), score)
    return sdg