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
    {"code": "B2", "role": "approver", "entity_slug": "transportation", "name": "Suresh Babu", "initials": "SB"},
    {"code": "B3", "role": "approver", "entity_slug": "power", "name": "Kavita Sharma", "initials": "KS"},
    {"code": "B4", "role": "approver", "entity_slug": "irrigation", "name": "Naresh Reddy", "initials": "NR"},
    {"code": "B5", "role": "approver", "entity_slug": "drinking-water", "name": "Pooja Nair", "initials": "PN"},
    {"code": "B6", "role": "approver", "entity_slug": "manufacturing", "name": "Suresh Menon", "initials": "SM"},
    {"code": "B7", "role": "approver", "entity_slug": "om", "name": "Anand Joshi", "initials": "AJ"},
    {"code": "B8", "role": "approver", "entity_slug": "megha-gas", "name": "Rohit Sharma", "initials": "RS"},
    {"code": "B9", "role": "approver", "entity_slug": "olectra", "name": "Divya Menon", "initials": "DM"},
    {"code": "B10", "role": "approver", "entity_slug": "drillmec", "name": "Sofia Ricci", "initials": "SR"},
    {"code": "B11", "role": "approver", "entity_slug": "icomm", "name": "Harsh Patel", "initials": "HP"},
    {"code": "C1", "role": "unit-admin", "entity_slug": "hydrocarbons", "name": "Naveen Kumar", "initials": "NK"},
    {"code": "C2", "role": "unit-admin", "entity_slug": "transportation", "name": "Arjun Mehta", "initials": "AM"},
    {"code": "C3", "role": "unit-admin", "entity_slug": "power", "name": "Suresh Babu", "initials": "SB"},
    {"code": "C4", "role": "unit-admin", "entity_slug": "irrigation", "name": "Vikram Shetty", "initials": "VS"},
    {"code": "C5", "role": "unit-admin", "entity_slug": "drinking-water", "name": "Lakshmi Iyer", "initials": "LI"},
    {"code": "C6", "role": "unit-admin", "entity_slug": "manufacturing", "name": "Rakesh Menon", "initials": "RM"},
    {"code": "C7", "role": "unit-admin", "entity_slug": "om", "name": "Girish Rao", "initials": "GR"},
    {"code": "C8", "role": "unit-admin", "entity_slug": "megha-gas", "name": "Prakash Jha", "initials": "PJ"},
    {"code": "C9", "role": "unit-admin", "entity_slug": "olectra", "name": "Anita Desai", "initials": "AD"},
    {"code": "C10", "role": "unit-admin", "entity_slug": "drillmec", "name": "Elena Rossi", "initials": "ER"},
    {"code": "C11", "role": "unit-admin", "entity_slug": "icomm", "name": "Arun Prasad", "initials": "AP"},
    {"code": "D1", "role": "esg-officer", "entity_slug": "group", "name": "Priya Nair", "initials": "PN"},
    {"code": "E1", "role": "group-admin", "entity_slug": "group", "name": "Sanjay Kulkarni", "initials": "SK"},
]


SECTIONS = [
    {"code": "A", "name": "Section A", "sub": "General Disclosures", "owner": "Company Secretariat"},
    {"code": "B", "name": "Section B", "sub": "Management & Process", "owner": "Sustainability Cell"},
    {"code": "C1", "name": "Principle 1", "sub": "Ethics & Transparency", "owner": "Legal & Compliance"},
    {"code": "C2", "name": "Principle 2", "sub": "Sustainable & Safe Goods", "owner": "Product & R&D"},
    {"code": "C3", "name": "Principle 3", "sub": "Employee Wellbeing", "owner": "Human Resources"},
    {"code": "C4", "name": "Principle 4", "sub": "Stakeholder Engagement", "owner": "Corporate Affairs"},
    {"code": "C5", "name": "Principle 5", "sub": "Human Rights", "owner": "Human Resources"},
    {"code": "C6", "name": "Principle 6", "sub": "Environment", "owner": "EHS & Sustainability"},
    {"code": "C7", "name": "Principle 7", "sub": "Public Policy Advocacy", "owner": "Legal & Compliance"},
    {"code": "C8", "name": "Principle 8", "sub": "Inclusive Growth", "owner": "CSR & Community"},
    {"code": "C9", "name": "Principle 9", "sub": "Consumer Value", "owner": "Customer Service"},
    {"code": "CORE", "name": "BRSR Core", "sub": "9 Attributes · 46 KPIs", "owner": "Sustainability Cell"},
]


FIELDS = [
    # Section A
    {"section_code": "A", "code": "A-I-1", "label": "Corporate Identity Number (CIN)", "field_type": "text", "value": "L40100TG1999PLC031717", "status": "complete"},
    {"section_code": "A", "code": "A-I-2", "label": "Name of the listed entity", "field_type": "text", "value": "Megha Engineering & Infrastructures Limited", "status": "complete"},
    {"section_code": "A", "code": "A-I-4", "label": "Registered office address", "field_type": "textarea", "value": "Plot No. 11, Software Units Layout, Infocity, Madhapur, Hyderabad 500081", "status": "complete"},
    {"section_code": "A", "code": "A-V", "label": "Number of employees / workers", "field_type": "text", "value": "79159", "status": "complete"},

    # Section B
    {"section_code": "B", "code": "B-1", "label": "Has the entity formed a sustainability committee?", "field_type": "textarea", "value": "Yes. ESG & Sustainability Committee of the Board - 3 independent directors and the MD.", "status": "complete"},
    {"section_code": "B", "code": "B-6", "label": "Frequency of ESG risk review by the Board", "field_type": "text", "value": "Quarterly", "status": "complete"},

    # Principle 1
    {"section_code": "C1", "code": "P1-E1", "label": "Percentage of anti-corruption training coverage", "field_type": "number", "unit": "%", "value": "96", "status": "complete"},

    # Principle 2
    {"section_code": "C2", "code": "P2-E1", "label": "R&D expenditure on sustainable products (%)", "field_type": "number", "unit": "%", "value": "", "status": "pending"},
    {"section_code": "C2", "code": "P2-E2", "label": "Recycled / sustainable input material (%)", "field_type": "number", "unit": "%", "value": "", "status": "pending"},
    {"section_code": "C2", "code": "P2-E3", "label": "Products with safety certification (nos)", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C2", "code": "P2-E4", "label": "Life-cycle assessment conducted for products?", "field_type": "textarea", "value": "", "status": "pending"},

    # Principle 3
    {"section_code": "C3", "code": "P3-E1", "label": "Total employees and workers", "field_type": "number", "value": "79159", "status": "complete"},
    {"section_code": "C3", "code": "P3-E5", "label": "Number of fatalities", "field_type": "number", "value": "3", "status": "complete"},

    # Principle 4
    {"section_code": "C4", "code": "P4-E1", "label": "Frequency of stakeholder engagement", "field_type": "text", "value": "", "status": "pending"},
    {"section_code": "C4", "code": "P4-E2", "label": "Number of stakeholder consultations held", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C4", "code": "P4-E3", "label": "Grievance redressal mechanism — describe", "field_type": "textarea", "value": "", "status": "pending"},

    # Principle 5
    {"section_code": "C5", "code": "P5-E1", "label": "Operations assessed for human rights risk (%)", "field_type": "number", "unit": "%", "value": "", "status": "pending"},
    {"section_code": "C5", "code": "P5-E2", "label": "Human rights complaints received", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C5", "code": "P5-E3", "label": "Employees trained on human rights (%)", "field_type": "number", "unit": "%", "value": "", "status": "pending"},

    # Principle 6
    {"section_code": "C6", "code": "P6-E1", "label": "Renewable energy consumed", "field_type": "number", "unit": "GJ", "value": "412880", "status": "complete"},
    {"section_code": "C6", "code": "P6-E3a", "label": "Scope 1 emissions", "field_type": "number", "unit": "tCO2e", "value": "218450", "status": "complete"},
    {"section_code": "C6", "code": "P6-E3b", "label": "Scope 2 emissions", "field_type": "number", "unit": "tCO2e", "value": "341220", "status": "complete"},
    {"section_code": "C6", "code": "P6-E3c", "label": "Scope 3 emissions", "field_type": "number", "unit": "tCO2e", "value": "1204660", "status": "flagged", "warn": "Scope 3 excludes Category 11 and 15 emissions."},
    {"section_code": "C6", "code": "P6-E2", "label": "Total water withdrawal", "field_type": "number", "unit": "KL", "value": "14820", "status": "complete"},

    # Principle 7
    {"section_code": "C7", "code": "P7-E1", "label": "Direct political contributions (Rs)", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C7", "code": "P7-E2", "label": "Trade / industry association memberships (nos)", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C7", "code": "P7-E3", "label": "Public policy positions taken — describe", "field_type": "textarea", "value": "", "status": "pending"},

    # Principle 8
    {"section_code": "C8", "code": "P8-E2", "label": "CSR expenditure (Rs crore)", "field_type": "number", "value": "186.4", "status": "complete"},

    # Principle 9
    {"section_code": "C9", "code": "P9-E1", "label": "Customer complaints received", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C9", "code": "P9-E2", "label": "Product recall incidents", "field_type": "number", "value": "", "status": "pending"},
    {"section_code": "C9", "code": "P9-E3", "label": "Customer satisfaction score (out of 5)", "field_type": "number", "value": "", "status": "pending"},

    # BRSR Core
    {"section_code": "CORE", "code": "Core-1", "label": "GHG footprint - Scope 1+2 intensity (tCO2e per Rs cr)", "field_type": "number", "value": "12.84", "status": "complete"},
    {"section_code": "CORE", "code": "Core-6", "label": "Gender diversity - percent women in workforce", "field_type": "number", "unit": "%", "value": "5.1", "status": "complete"},
]


async def seed():
    await init_db()
    async with SessionLocal() as db:
        for M in (BrsrField, BrsrSection, User, Entity):
            rows = (await db.execute(select(M))).scalars().all()
            for r in rows:
                await db.delete(r)
        await db.commit()

        for e in ENTITIES:
            db.add(Entity(**e))
        for u in USERS:
            db.add(User(**u, password_hash=hash_password("demo")))
        for s in SECTIONS:
            db.add(BrsrSection(**s))

        all_units = [
            "hydrocarbons", "transportation", "power", "irrigation",
            "drinking-water", "manufacturing", "om",
            "megha-gas", "olectra", "drillmec", "icomm",
        ]
        for entity_slug in all_units:
            for f in FIELDS:
                db.add(BrsrField(entity_slug=entity_slug, **f))

        await db.commit()
        print("Seeded successfully")
        print(f"  Entities:   {len(ENTITIES)}")
        print(f"  Users:      {len(USERS)}")
        print(f"  Sections:   {len(SECTIONS)}")
        print(f"  Fields:     {len(FIELDS) * len(all_units)}")


if __name__ == "__main__":
    asyncio.run(seed())