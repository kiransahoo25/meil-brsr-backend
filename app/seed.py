import asyncio
from sqlmodel import select
from app.database import SessionLocal, init_db
from app.models import Entity, User, BrsrSection, BrsrField
from app.security import hash_password


ENTITIES = [
    {"slug": "group", "name": "MEIL Group (Consolidated)", "type": "Group", "code": "GRP", "progress": 68},
    {"slug": "meil", "name": "MEIL – Parent Entity", "type": "Parent Entity", "parent_slug": None, "code": "MEIL", "progress": 74},
    {"slug": "hydrocarbons", "name": "Hydrocarbons BU", "type": "Business Unit", "parent_slug": "meil", "code": "A1", "progress": 71},
    {"slug": "transportation", "name": "Transportation BU", "type": "Business Unit", "parent_slug": "meil", "code": "A2", "progress": 66},
    {"slug": "power", "name": "Power BU", "type": "Business Unit", "parent_slug": "meil", "code": "A3", "progress": 79},
    {"slug": "irrigation", "name": "Irrigation BU", "type": "Business Unit", "parent_slug": "meil", "code": "A4", "progress": 83},
    {"slug": "drinking-water", "name": "Drinking Water BU", "type": "Business Unit", "parent_slug": "meil", "code": "A5", "progress": 77},
    {"slug": "manufacturing", "name": "Manufacturing BU", "type": "Business Unit", "parent_slug": "meil", "code": "A6", "progress": 62},
    {"slug": "om", "name": "Operation & Maintenance BU", "type": "Business Unit", "parent_slug": "meil", "code": "A7", "progress": 58},
    {"slug": "megha-gas", "name": "Megha Gas", "type": "Subsidiary", "parent_slug": "group", "code": "A8", "progress": 69},
    {"slug": "olectra", "name": "Olectra Green Tech", "type": "Subsidiary", "parent_slug": "group", "code": "A9", "progress": 54},
    {"slug": "drillmec", "name": "Drillmec", "type": "Subsidiary", "parent_slug": "group", "code": "A10", "progress": 47},
    {"slug": "icomm", "name": "ICOMM Tele Limited", "type": "Subsidiary", "parent_slug": "group", "code": "A11", "progress": 61},
]


USERS = [
    {"code": "A1", "role": "data-entry", "entity_slug": "hydrocarbons", "name": "Ravi Verma", "initials": "RV"},
    {"code": "A2", "role": "data-entry", "entity_slug": "transportation", "name": "Anil Kumar", "initials": "AK"},
    {"code": "A3", "role": "data-entry", "entity_slug": "power", "name": "Kiran Rao", "initials": "KR"},
    {"code": "A4", "role": "data-entry", "entity_slug": "irrigation", "name": "Ravi Teja", "initials": "RT"},
    {"code": "A5", "role": "data-entry", "entity_slug": "drinking-water", "name": "Vikram Shetty", "initials": "VS"},
    {"code": "A6", "role": "data-entry", "entity_slug": "manufacturing", "name": "Rakesh Menon", "initials": "RM"},
    {"code": "A7", "role": "data-entry", "entity_slug": "om", "name": "Ganesh Patil", "initials": "GP"},
    {"code": "A8", "role": "data-entry", "entity_slug": "megha-gas", "name": "Deepak Shah", "initials": "DS"},
    {"code": "A9", "role": "data-entry", "entity_slug": "olectra", "name": "Sunita Rao", "initials": "SR"},
    {"code": "A10", "role": "data-entry", "entity_slug": "drillmec", "name": "Marco Bellini", "initials": "MB"},
    {"code": "A11", "role": "data-entry", "entity_slug": "icomm", "name": "Arun Prasad", "initials": "AP"},
    {"code": "B1", "role": "approver", "entity_slug": "hydrocarbons", "name": "Meera Iyer", "initials": "MI"},
    {"code": "B3", "role": "approver", "entity_slug": "power", "name": "Kavita Sharma", "initials": "KS"},
    {"code": "B4", "role": "approver", "entity_slug": "irrigation", "name": "Naresh Reddy", "initials": "NR"},
    {"code": "B8", "role": "approver", "entity_slug": "megha-gas", "name": "Rohit Sharma", "initials": "RS"},
    {"code": "C1", "role": "unit-admin", "entity_slug": "hydrocarbons", "name": "Naveen Kumar", "initials": "NK"},
    {"code": "C3", "role": "unit-admin", "entity_slug": "power", "name": "Suresh Babu", "initials": "SB"},
    {"code": "C4", "role": "unit-admin", "entity_slug": "irrigation", "name": "Vikram Shetty", "initials": "VS"},
    {"code": "C8", "role": "unit-admin", "entity_slug": "megha-gas", "name": "Prakash Jha", "initials": "PJ"},
    {"code": "D1", "role": "esg-officer", "entity_slug": "group", "name": "Priya Nair", "initials": "PN"},
    {"code": "E1", "role": "group-admin", "entity_slug": "group", "name": "Sanjay Kulkarni", "initials": "SK"},
]


SECTIONS = [
    {"code": "A", "name": "Section A", "sub": "General Disclosures", "owner": "Company Secretariat"},
    {"code": "B", "name": "Section B", "sub": "Management & Process", "owner": "Sustainability Cell"},
    {"code": "C1", "name": "Principle 1", "sub": "Ethics & Transparency", "owner": "Legal & Compliance"},
    {"code": "C3", "name": "Principle 3", "sub": "Employee Wellbeing", "owner": "Human Resources"},
    {"code": "C6", "name": "Principle 6", "sub": "Environment", "owner": "EHS & Sustainability"},
    {"code": "C8", "name": "Principle 8", "sub": "Inclusive Growth", "owner": "CSR & Community"},
    {"code": "CORE", "name": "BRSR Core", "sub": "9 Attributes · 46 KPIs", "owner": "Sustainability Cell"},
]


FIELDS = [
    {"section_code": "A", "code": "A-I-1", "label": "Corporate Identity Number (CIN)", "field_type": "text", "value": "L40100TG1999PLC031717", "status": "complete"},
    {"section_code": "A", "code": "A-I-2", "label": "Name of the listed entity", "field_type": "text", "value": "Megha Engineering & Infrastructures Limited", "status": "complete"},
    {"section_code": "A", "code": "A-I-4", "label": "Registered office address", "field_type": "textarea", "value": "Plot No. 11, Software Units Layout, Infocity, Madhapur, Hyderabad 500081", "status": "complete"},
    {"section_code": "A", "code": "A-V", "label": "Number of employees / workers", "field_type": "text", "value": "79159", "status": "complete"},
    {"section_code": "B", "code": "B-1", "label": "Has the entity formed a sustainability committee?", "field_type": "textarea", "value": "Yes. ESG & Sustainability Committee of the Board - 3 independent directors and the MD.", "status": "complete"},
    {"section_code": "B", "code": "B-6", "label": "Frequency of ESG risk review by the Board", "field_type": "text", "value": "Quarterly", "status": "complete"},
    {"section_code": "C1", "code": "P1-E1", "label": "Percentage of anti-corruption training coverage", "field_type": "number", "unit": "%", "value": "96", "status": "complete"},
    {"section_code": "C3", "code": "P3-E1", "label": "Total employees and workers", "field_type": "number", "value": "79159", "status": "complete"},
    {"section_code": "C3", "code": "P3-E5", "label": "Number of fatalities", "field_type": "number", "value": "3", "status": "complete"},
    {"section_code": "C6", "code": "P6-E1", "label": "Renewable energy consumed", "field_type": "number", "unit": "GJ", "value": "412880", "status": "complete"},
    {"section_code": "C6", "code": "P6-E3a", "label": "Scope 1 emissions", "field_type": "number", "unit": "tCO2e", "value": "218450", "status": "complete"},
    {"section_code": "C6", "code": "P6-E3b", "label": "Scope 2 emissions", "field_type": "number", "unit": "tCO2e", "value": "341220", "status": "complete"},
    {"section_code": "C6", "code": "P6-E3c", "label": "Scope 3 emissions", "field_type": "number", "unit": "tCO2e", "value": "1204660", "status": "flagged", "warn": "Scope 3 excludes Category 11 and 15 emissions."},
    {"section_code": "C6", "code": "P6-E2", "label": "Total water withdrawal", "field_type": "number", "unit": "KL", "value": "14820", "status": "complete"},
    {"section_code": "C8", "code": "P8-E2", "label": "CSR expenditure (Rs crore)", "field_type": "number", "value": "186.4", "status": "complete"},
    {"section_code": "CORE", "code": "Core-1", "label": "GHG footprint - Scope 1+2 intensity (tCO2e per Rs cr)", "field_type": "number", "value": "12.84", "status": "complete"},
    {"section_code": "CORE", "code": "Core-6", "label": "Gender diversity - percent women in workforce", "field_type": "number", "unit": "%", "value": "5.1", "status": "complete"},
]


async def seed():
    await init_db()
    async with SessionLocal() as db:
        # Idempotent: clear existing rows
        for M in (BrsrField, BrsrSection, User, Entity):
            result = await db.execute(select(M))
            rows = result.scalars().all()
            for r in rows:
                await db.delete(r)
        await db.commit()

        for e in ENTITIES:
            db.add(Entity(**e))
        for u in USERS:
            db.add(User(**u, password_hash=hash_password("demo")))
        for s in SECTIONS:
            db.add(BrsrSection(**s))

        demo_entities = ["hydrocarbons", "power", "irrigation", "megha-gas"]
        for entity_slug in demo_entities:
            for f in FIELDS:
                db.add(BrsrField(entity_slug=entity_slug, **f))

        await db.commit()
        print("Seeded successfully")
        print(f"  Entities:   {len(ENTITIES)}")
        print(f"  Users:      {len(USERS)}")
        print(f"  Sections:   {len(SECTIONS)}")
        print(f"  Fields:     {len(FIELDS) * len(demo_entities)}")


if __name__ == "__main__":
    asyncio.run(seed())