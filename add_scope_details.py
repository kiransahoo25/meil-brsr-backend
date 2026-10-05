"""One-time script: add detailed Scope 1/2/3 breakdown as a new section C6D.

Adds 24 fields to every reporting entity:
  Scope 1 → 5 fields (stationary, mobile, fugitive, process, total)
  Scope 2 → 3 fields (location-based, market-based, total)
  Scope 3 → 16 fields (15 GHG Protocol categories + total)
"""

import asyncio
from sqlmodel import select
from app.database import SessionLocal
from app.models import BrsrSection, BrsrField


SECTION = {
    "code": "C6D",
    "name": "Principle 6 · Detail",
    "sub": "Scope 1 / 2 / 3 Breakdown",
    "owner": "EHS & Sustainability",
}


SCOPE_FIELDS = [
    # ---------- SCOPE 1 — Direct Emissions (5 fields) ----------
    {"code": "P6-S1-STA", "label": "Scope 1 · Stationary Combustion (boilers, generators, furnaces)", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S1-MOB", "label": "Scope 1 · Mobile Combustion (company vehicles, machinery)", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S1-FUG", "label": "Scope 1 · Fugitive Emissions (refrigerants, AC, methane leaks)", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S1-PRO", "label": "Scope 1 · Process Emissions (industrial chemical reactions)", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S1-TOT", "label": "Scope 1 · Total Direct Emissions", "field_type": "number", "unit": "tCO2e"},

    # ---------- SCOPE 2 — Indirect from Purchased Energy (3 fields) ----------
    {"code": "P6-S2-LOC", "label": "Scope 2 · Location-based Method (grid average EF)", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S2-MKT", "label": "Scope 2 · Market-based Method (supplier-specific EF)", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S2-TOT", "label": "Scope 2 · Total Indirect Emissions (as reported)", "field_type": "number", "unit": "tCO2e"},

    # ---------- SCOPE 3 — Value Chain (16 fields) ----------
    {"code": "P6-S3-C01", "label": "Scope 3 · Cat 1 · Purchased Goods & Services", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C02", "label": "Scope 3 · Cat 2 · Capital Goods", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C03", "label": "Scope 3 · Cat 3 · Fuel & Energy Related Activities", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C04", "label": "Scope 3 · Cat 4 · Upstream Transportation & Distribution", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C05", "label": "Scope 3 · Cat 5 · Waste Generated in Operations", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C06", "label": "Scope 3 · Cat 6 · Business Travel", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C07", "label": "Scope 3 · Cat 7 · Employee Commuting", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C08", "label": "Scope 3 · Cat 8 · Upstream Leased Assets", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C09", "label": "Scope 3 · Cat 9 · Downstream Transportation & Distribution", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C10", "label": "Scope 3 · Cat 10 · Processing of Sold Products", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C11", "label": "Scope 3 · Cat 11 · Use of Sold Products", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C12", "label": "Scope 3 · Cat 12 · End-of-life of Sold Products", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C13", "label": "Scope 3 · Cat 13 · Downstream Leased Assets", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C14", "label": "Scope 3 · Cat 14 · Franchises", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-C15", "label": "Scope 3 · Cat 15 · Investments", "field_type": "number", "unit": "tCO2e"},
    {"code": "P6-S3-TOT", "label": "Scope 3 · Total Value Chain Emissions", "field_type": "number", "unit": "tCO2e"},
]


ALL_UNITS = [
    "hydrocarbons", "transportation", "power", "irrigation",
    "drinking-water", "manufacturing", "om",
    "megha-gas", "olectra", "drillmec", "icomm",
]


async def add_scope_section():
    async with SessionLocal() as db:
        # 1. Add the C6D section (if missing)
        existing = await db.execute(
            select(BrsrSection).where(BrsrSection.code == SECTION["code"])
        )
        if existing.scalars().first():
            print(f"Section {SECTION['code']} already exists — skipping section creation")
        else:
            db.add(BrsrSection(**SECTION))
            print(f"+ Section {SECTION['code']} — {SECTION['name']}")
        await db.commit()

        # 2. Add all 24 fields for each entity (if not already present)
        total_added = 0
        for entity_slug in ALL_UNITS:
            # Check whether this entity already has fields for C6D
            check = await db.execute(
                select(BrsrField)
                .where(BrsrField.entity_slug == entity_slug)
                .where(BrsrField.section_code == "C6D")
                .limit(1)
            )
            if check.scalars().first():
                print(f"  {entity_slug}: C6D fields exist — skipping")
                continue

            for f in SCOPE_FIELDS:
                db.add(BrsrField(
                    entity_slug=entity_slug,
                    section_code="C6D",
                    code=f["code"],
                    label=f["label"],
                    field_type=f["field_type"],
                    unit=f.get("unit"),
                    required=True,
                    value="",
                    status="pending",
                ))
                total_added += 1
            print(f"  {entity_slug}: +{len(SCOPE_FIELDS)} fields")

        await db.commit()
        print(f"\n✓ Added section C6D and {total_added} total fields")


if __name__ == "__main__":
    asyncio.run(add_scope_section())