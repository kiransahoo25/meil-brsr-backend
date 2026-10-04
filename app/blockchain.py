"""Cryptographic integrity module for the MEIL BRSR Portal.

Creates SHA-256 fingerprints of submitted data so that any future
modification is provably detectable.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def create_data_fingerprint(data: Any) -> str:
    """
    Create a deterministic SHA-256 hash of any data structure.

    Two calls with the same data return the same hash.
    Any change to the data (even one character) produces a completely
    different hash — this is the core of tamper detection.
    """
    # Serialize with sorted keys so the output is deterministic
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_fingerprint(data: Any, expected_hash: str) -> bool:
    """
    Recompute the hash of the data and compare it against a stored hash.
    Returns True if they match (data is untouched), False if tampered.
    """
    actual = create_data_fingerprint(data)
    return actual == expected_hash


def anchor_fingerprint(fingerprint: str) -> dict:
    """
    Simulate blockchain anchoring.

    In a full production system this would POST to a public
    OpenTimestamps calendar server (free) which batches the hash
    into a Bitcoin block. For the hackathon demo, we return a
    structurally-correct proof object that shows what the real
    anchor would contain.
    """
    return {
        "fingerprint": fingerprint,
        "algorithm": "SHA-256",
        "anchored_at": datetime.now(timezone.utc).isoformat(),
        "chain": "Bitcoin (via OpenTimestamps)",
        "status": "anchored",
        # A real OTS proof would be a base64 string. We simulate its shape.
        "proof": f"OTS::{fingerprint[:16]}...{fingerprint[-16:]}",
    }


def verify_proof(fingerprint: str, proof_dict: dict) -> dict:
    """
    Verify that a stored proof matches a fingerprint.
    For the demo, we do a structural verification.
    """
    matches = proof_dict.get("fingerprint") == fingerprint
    return {
        "verified": matches,
        "fingerprint": fingerprint,
        "algorithm": proof_dict.get("algorithm", "SHA-256"),
        "chain": proof_dict.get("chain", "Bitcoin (via OpenTimestamps)"),
        "anchored_at": proof_dict.get("anchored_at"),
        "message": (
            "Data integrity confirmed — no tampering detected."
            if matches
            else "WARNING: Fingerprint mismatch — data may have been altered."
        ),
    }


def build_submission_payload(submission: Any, fields: list) -> dict:
    """
    Build the canonical payload that gets hashed when a section is submitted.
    Only the values that matter (datapoint code + value) are included so
    the fingerprint is stable and meaningful.
    """
    return {
        "submission_id": submission.submission_id,
        "entity_slug": submission.entity_slug,
        "section_code": submission.section_code,
        "submitted_by": submission.submitted_by,
        "fields": sorted(
            [
                {
                    "code": f.code,
                    "value": f.value,
                }
                for f in fields
                if getattr(f, "value", None)
            ],
            key=lambda x: x["code"],
        ),
    }