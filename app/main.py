from email.mime import text
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
import base64
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from sqlmodel import select
import jwt as pyjwt
from contextlib import asynccontextmanager
import uuid
from fastapi.responses import StreamingResponse
import csv
from io import StringIO
from app.config import settings
from app.database import get_db, init_db, engine
from app.models import Entity, User, BrsrSection, BrsrField, Submission, AuditLog, Comment, ValidationIssue, Evidence
from app.security import hash_password, verify_password, create_access_token, decode_token
from app.pdf_report import build_brsr_pdf
from app.sdg_pdf import build_sdg_pdf
from app.validation import run_rules, RULE_CATALOG
from app.models import ValidationIssue
from app.chatbot import find_answer, get_greeting, get_suggestions
from app.ai_gap_analysis import run_gap_analysis
from pydantic import BaseModel
from pydantic import BaseModel
from sqlalchemy import text
from pydantic import BaseModel
from app.carbon_factors import (
    calc_electricity_emissions,
    calc_fuel_emissions,
    calc_renewable_offset,
    convert_units,
    get_all_reference_data,
)

class SecurityLog(BaseModel):
    method: str


security_scheme = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    await init_db()
    # Warm up the connection pool so the first real request is fast
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pass
    yield
    await engine.dispose()


app = FastAPI(title="MEIL BRSR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
      allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://meil-brsr-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security_scheme)):
    try:
        return decode_token(creds.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------------- AUTH ----------------
@app.post("/api/auth/login")
async def login(code: str, password: str, db=Depends(get_db)):
    result = await db.execute(select(User).where(User.code == code.upper()))
    user = result.scalars().first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({
        "sub": user.code,
        "role": user.role,
        "entity": user.entity_slug,
        "name": user.name,
        "initials": user.initials,
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "code": user.code,
            "name": user.name,
            "role": user.role,
            "initials": user.initials,
            "entity": user.entity_slug,
        },
    }


# ---------------- HEALTH ----------------
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------- ENTITIES ----------------
@app.get("/api/entities")
async def list_entities(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Entity))
    entities = result.scalars().all()
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        entities = [e for e in entities if e.slug == user["entity"]]
    return entities


# ---------------- SECTIONS ----------------
@app.get("/api/collection/sections")
async def list_sections(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(BrsrSection))
    return result.scalars().all()


@app.get("/api/collection/entity/{entity_slug}")
async def get_all_entity_fields(
    entity_slug: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(BrsrField).where(BrsrField.entity_slug == entity_slug)
    )
    fields = result.scalars().all()
    return [
        {
            "id": f.id,
            "section_code": f.section_code,
            "code": f.code,
            "label": f.label,
            "value": f.value,
            "unit": f.unit,
            "status": f.status,
            "warn": f.warn,
            "required": f.required,
        }
        for f in fields
    ]


@app.get("/api/collection/{entity_slug}/{section_code}")
async def get_fields(
    entity_slug: str,
    section_code: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(BrsrField)
        .where(BrsrField.entity_slug == entity_slug)
        .where(BrsrField.section_code == section_code)
    )
    return result.scalars().all()


@app.patch("/api/collection/field/{field_id}")
async def update_field(
    field_id: int,
    value: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] != "data-entry":
        raise HTTPException(status_code=403, detail="Not allowed")
    field = await db.get(BrsrField, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    old = field.value
    field.value = value
    field.status = "complete"
    db.add(field)
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=field.entity_slug,
        datapoint=field.code,
        action="Value updated",
        from_value=old[:50],
        to_value=value[:50],
    ))
    await db.commit()
    return {"status": "saved"}


@app.post("/api/collection/submit/{entity_slug}/{section_code}")
async def submit_section(
    entity_slug: str,
    section_code: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("data-entry", "unit-admin"):
        raise HTTPException(status_code=403, detail="Not allowed to submit")

    existing_result = await db.execute(
        select(Submission)
        .where(Submission.entity_slug == entity_slug)
        .where(Submission.section_code == section_code)
    )
    existing = existing_result.scalars().first()

    if existing:
        existing.state = "Submitted"
        existing.submitted_by = user["name"]
        existing.approver = None
        existing.remarks = ""
        sub_id = existing.submission_id
    else:
        sub_id = f"S-{uuid.uuid4().hex[:6].upper()}"
        db.add(Submission(
            submission_id=sub_id,
            entity_slug=entity_slug,
            section_code=section_code,
            state="Submitted",
            submitted_by=user["name"],
        ))

    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=entity_slug,
        datapoint=section_code,
        action="Submitted for review",
        from_value="Draft",
        to_value="Submitted",
    ))
    await db.commit()
    return {"status": "submitted", "submission_id": sub_id}


@app.post("/api/collection/submit-all/{entity_slug}")
async def submit_all_sections(
    entity_slug: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("data-entry", "unit-admin"):
        raise HTTPException(status_code=403, detail="Not allowed to submit")

    sec_result = await db.execute(select(BrsrSection))
    sections = sec_result.scalars().all()

    submitted = []
    skipped = []

    for sec in sections:
        f_result = await db.execute(
            select(BrsrField)
            .where(BrsrField.entity_slug == entity_slug)
            .where(BrsrField.section_code == sec.code)
        )
        fields = f_result.scalars().all()

        if not fields:
            continue

        incomplete = sum(1 for f in fields if f.required and not f.value)
        if incomplete > 0:
            skipped.append({
                "section": sec.name,
                "reason": f"{incomplete} required field(s) missing",
            })
            continue

        existing_result = await db.execute(
            select(Submission)
            .where(Submission.entity_slug == entity_slug)
            .where(Submission.section_code == sec.code)
        )
        existing = existing_result.scalars().first()

        if existing:
            existing.state = "Submitted"
            existing.submitted_by = user["name"]
            existing.approver = None
            existing.remarks = ""
        else:
            sub_id = f"S-{uuid.uuid4().hex[:6].upper()}"
            db.add(Submission(
                submission_id=sub_id,
                entity_slug=entity_slug,
                section_code=sec.code,
                state="Submitted",
                submitted_by=user["name"],
            ))

        db.add(AuditLog(
            user_code=user["sub"],
            user_name=user["name"],
            role=user["role"],
            entity_slug=entity_slug,
            datapoint=sec.code,
            action="Submitted for review",
            from_value="Draft",
            to_value="Submitted",
        ))
        submitted.append(sec.name)

    await db.commit()
    return {
        "submitted_count": len(submitted),
        "submitted_sections": submitted,
        "skipped_count": len(skipped),
        "skipped_sections": skipped,
    }


# ---------------- APPROVALS ----------------
@app.get("/api/approvals/list")
async def list_approvals(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Submission))
    subs = result.scalars().all()

    if user["role"] in ("approver", "unit-admin"):
        subs = [s for s in subs if s.entity_slug == user["entity"]]

    out = []
    for s in subs:
        sec_result = await db.execute(
            select(BrsrSection).where(BrsrSection.code == s.section_code)
        )
        sec = sec_result.scalars().first()

        ent_result = await db.execute(
            select(Entity).where(Entity.slug == s.entity_slug)
        )
        ent = ent_result.scalars().first()

        out.append({
            "id": s.submission_id,
            "entity_slug": s.entity_slug,
            "entity_name": ent.name if ent else s.entity_slug,
            "section_code": s.section_code,
            "section_name": sec.name if sec else s.section_code,
            "state": s.state,
            "submitted_by": s.submitted_by,
            "approver": s.approver or "—",
            "remarks": s.remarks or "",
        })
    return out


@app.post("/api/approvals/{submission_id}/approve")
async def approve_submission(
    submission_id: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("approver", "unit-admin", "esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    sub.state = "Approved"
    sub.approver = user["name"]
    sub.remarks = ""
    db.add(sub)
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=sub.entity_slug,
        datapoint=sub.section_code,
        action="Approved",
        from_value="Submitted",
        to_value="Approved",
    ))
    await db.commit()
    return {"status": "approved"}


@app.post("/api/approvals/{submission_id}/reject")
async def reject_submission(
    submission_id: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("approver", "unit-admin", "esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    sub.state = "Rejected"
    sub.approver = user["name"]
    sub.remarks = "Data does not reconcile with source records."
    db.add(sub)
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=sub.entity_slug,
        datapoint=sub.section_code,
        action="Rejected",
        from_value="Submitted",
        to_value="Rejected",
    ))
    await db.commit()
    return {"status": "rejected"}


@app.post("/api/approvals/{submission_id}/request-changes")
async def request_changes(
    submission_id: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("approver", "unit-admin", "esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    sub.state = "Changes Requested"
    sub.approver = user["name"]
    sub.remarks = "Please re-check coverage and attach supporting evidence."
    db.add(sub)
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=sub.entity_slug,
        datapoint=sub.section_code,
        action="Changes Requested",
        from_value="Submitted",
        to_value="Changes Requested",
    ))
    await db.commit()
    return {"status": "changes_requested"}


# ---------------- COMMENTS ----------------
@app.get("/api/approvals/{submission_id}/comments")
async def list_comments(
    submission_id: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.submission_id == submission_id)
        .order_by(Comment.id.asc())
    )
    comments = result.scalars().all()
    return [
        {
            "id": c.id,
            "author_code": c.author_code,
            "author_name": c.author_name,
            "author_role": c.author_role,
            "body": c.body,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in comments
    ]


@app.post("/api/approvals/{submission_id}/comment")
async def add_comment(
    submission_id: str,
    body: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if not body.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    c = Comment(
        submission_id=submission_id,
        author_code=user["sub"],
        author_name=user["name"],
        author_role=user["role"],
        body=body.strip(),
    )
    db.add(c)
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=user["entity"],
        datapoint=submission_id,
        action="Commented",
        from_value="",
        to_value=body[:80],
    ))
    await db.commit()
    return {"status": "created", "id": c.id}


# ---------------- CONSOLIDATED ESG ----------------
@app.get("/api/esg/consolidated")
async def esg_consolidated(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] not in ("esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    ent_result = await db.execute(select(Entity))
    entities = ent_result.scalars().all()
    units = [e for e in entities if e.type in ("Business Unit", "Subsidiary")]

    sec_result = await db.execute(select(BrsrSection))
    sections = sec_result.scalars().all()

    out = []
    for u in units:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.entity_slug == u.slug)
        )
        fields = f_result.scalars().all()

        sec_progress = []
        for s in sections:
            sec_fields = [f for f in fields if f.section_code == s.code]
            done = sum(1 for f in sec_fields if f.value)
            pct = int((done / len(sec_fields)) * 100) if sec_fields else 0
            sec_progress.append({
                "code": s.code,
                "name": s.name,
                "progress": pct,
            })

        filled = sum(1 for f in fields if f.value)
        total = len(fields)
        overall = int((filled / total) * 100) if total else 0

        sub_result = await db.execute(
            select(Submission).where(Submission.entity_slug == u.slug)
        )
        subs = sub_result.scalars().all()

        out.append({
            "slug": u.slug,
            "name": u.name,
            "type": u.type,
            "code": u.code,
            "overall": overall,
            "sections": sec_progress,
            "submitted": sum(1 for x in subs if x.state == "Submitted"),
            "approved": sum(1 for x in subs if x.state == "Approved"),
            "rejected": sum(1 for x in subs if x.state == "Rejected"),
        })

    return out


# ---------------- DASHBOARD ----------------
@app.get("/api/dashboard/stats")
async def dashboard_stats(
    entity_slug: str = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if entity_slug and user["role"] in ("esg-officer", "group-admin"):
        target = entity_slug
    elif user["role"] in ("esg-officer", "group-admin"):
        target = None
    else:
        target = user["entity"]

    result = await db.execute(select(BrsrSection))
    sections = result.scalars().all()

    section_progress = []
    for s in sections:
        q = select(BrsrField).where(BrsrField.section_code == s.code)
        if target:
            q = q.where(BrsrField.entity_slug == target)
        f_result = await db.execute(q)
        fields = f_result.scalars().all()
        done = sum(1 for f in fields if f.value)
        pct = int((done / len(fields)) * 100) if fields else 0
        section_progress.append({
            "code": s.code,
            "name": s.name,
            "sub": s.sub,
            "progress": pct,
        })

    sub_result = await db.execute(select(Submission))
    subs = sub_result.scalars().all()
    if target:
        subs = [x for x in subs if x.entity_slug == target]

    overall = (
        sum(x["progress"] for x in section_progress) // max(len(section_progress), 1)
        if section_progress
        else 0
    )

    return {
        "overallProgress": overall,
        "openIssues": 0,
        "highSeverity": 0,
        "pendingApprovals": sum(1 for x in subs if x.state == "Submitted"),
        "assuranceReady": 0,
        "sectionProgress": section_progress,
        "targetEntity": target or "all",
    }


# ---------------- BRSR PDF REPORT ----------------
@app.get("/api/reports/brsr-pdf")
async def brsr_pdf_report(
    entity_slug: str = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        target_slug = user["entity"]
    else:
        target_slug = entity_slug or user["entity"]

    ent_result = await db.execute(select(Entity).where(Entity.slug == target_slug))
    entity = ent_result.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    sec_result = await db.execute(select(BrsrSection))
    sections = sec_result.scalars().all()

    field_result = await db.execute(
        select(BrsrField).where(BrsrField.entity_slug == target_slug)
    )
    fields = field_result.scalars().all()

    pdf_bytes = build_brsr_pdf(
        entity={
            "name": entity.name,
            "type": entity.type,
            "code": entity.code,
        },
        sections=[{"code": s.code, "name": s.name, "sub": s.sub} for s in sections],
        fields=[{"section_code": f.section_code, "value": f.value} for f in fields],
        user_name=user["name"],
        user_role=user["role"],
    )

    safe_name = entity.name.replace(" ", "_").replace("/", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="MEIL_BRSR_{safe_name}_FY2526.pdf"'
        },
    )

    # ---------------- GROUP OVERVIEW ----------------
@app.get("/api/group/overview")
async def group_overview(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "group-admin":
        raise HTTPException(status_code=403, detail="Group Admin only")

    EQUITY = {
        "hydrocarbons": 100.0,
        "transportation": 100.0,
        "power": 100.0,
        "irrigation": 100.0,
        "drinking-water": 100.0,
        "manufacturing": 100.0,
        "om": 100.0,
        "megha-gas": 100.0,
        "olectra": 74.0,
        "drillmec": 100.0,
        "icomm": 51.0,
    }

    ent_result = await db.execute(select(Entity))
    entities = ent_result.scalars().all()
    units = [e for e in entities if e.type in ("Business Unit", "Subsidiary")]

    sec_result = await db.execute(select(BrsrSection))
    sections = sec_result.scalars().all()

    unit_data = []
    for u in units:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.entity_slug == u.slug)
        )
        fields = f_result.scalars().all()

        sec_progress = []
        for s in sections:
            sec_fields = [f for f in fields if f.section_code == s.code]
            done = sum(1 for f in sec_fields if f.value)
            pct = int((done / len(sec_fields)) * 100) if sec_fields else 0
            sec_progress.append({
                "code": s.code,
                "name": s.name,
                "sub": s.sub,
                "progress": pct,
            })

        filled = sum(1 for f in fields if f.value)
        total = len(fields)
        overall = int((filled / total) * 100) if total else 0

        sub_result = await db.execute(
            select(Submission).where(Submission.entity_slug == u.slug)
        )
        subs = sub_result.scalars().all()

        submitted = sum(1 for x in subs if x.state == "Submitted")
        approved = sum(1 for x in subs if x.state == "Approved")
        rejected = sum(1 for x in subs if x.state == "Rejected")
        changes = sum(1 for x in subs if x.state == "Changes Requested")

        improvements = []

        for s in subs:
            if s.state == "Rejected":
                sec = next((x for x in sections if x.code == s.section_code), None)
                if sec:
                    improvements.append({
                        "priority": "high",
                        "icon": "❌",
                        "text": f"Rejected submission in {sec.name} — review remarks and resubmit",
                    })

        for s in subs:
            if s.state == "Changes Requested":
                sec = next((x for x in sections if x.code == s.section_code), None)
                if sec:
                    improvements.append({
                        "priority": "medium",
                        "icon": "↩",
                        "text": f"Revisions pending for {sec.name}",
                    })

        low_sections = sorted(sec_progress, key=lambda x: x["progress"])[:2]
        for s in low_sections:
            if s["progress"] < 100:
                improvements.append({
                    "priority": "low" if s["progress"] > 50 else "medium",
                    "icon": "📝",
                    "text": f"Complete {s['name']} — currently at {s['progress']}%",
                })

        unit_data.append({
            "slug": u.slug,
            "name": u.name,
            "code": u.code,
            "type": u.type,
            "ownership_pct": EQUITY.get(u.slug, 100.0),
            "overall": overall,
            "sections": sec_progress,
            "submitted": submitted,
            "approved": approved,
            "rejected": rejected,
            "changes": changes,
            "improvements": improvements[:4],
        })

    avg_overall = (
        int(sum(x["overall"] for x in unit_data) / len(unit_data)) if unit_data else 0
    )
    total_submitted = sum(x["submitted"] for x in unit_data)
    total_approved = sum(x["approved"] for x in unit_data)
    total_rejected = sum(x["rejected"] for x in unit_data)
    total_improvements = sum(len(x["improvements"]) for x in unit_data)

    return {
        "totals": {
            "units": len(unit_data),
            "avgProgress": avg_overall,
            "submitted": total_submitted,
            "approved": total_approved,
            "rejected": total_rejected,
            "improvements": total_improvements,
        },
        "units": unit_data,
    }
    # ---------------- SDG PDF REPORT ----------------
@app.get("/api/reports/sdg-pdf")
async def sdg_pdf_report(
    entity_slug: str = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        target_slug = user["entity"]
    else:
        target_slug = entity_slug or user["entity"]

    ent_result = await db.execute(select(Entity).where(Entity.slug == target_slug))
    entity = ent_result.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    pdf_bytes = build_sdg_pdf(
        entity={
            "name": entity.name,
            "type": entity.type,
            "code": entity.code,
        },
        user_name=user["name"],
        user_role=user["role"],
    )

    safe_name = entity.name.replace(" ", "_").replace("/", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="MEIL_SDG_{safe_name}_FY2526.pdf"'
        },
    )

# ---------------- VALIDATION ----------------
@app.get("/api/validation/issues")
async def list_validation_issues(
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(ValidationIssue).order_by(ValidationIssue.id.desc())
    )
    issues = result.scalars().all()

    # Scope: non-group roles see only their entity
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        issues = [i for i in issues if i.entity_slug == user["entity"]]

    return [
        {
            "id": i.id,
            "entity_slug": i.entity_slug,
            "section_code": i.section_code,
            "datapoint": i.datapoint,
            "field_label": i.field_label,
            "severity": i.severity,
            "rule_name": i.rule_name,
            "message": i.message,
            "status": i.status,
            "resolved_by": i.resolved_by,
            "created_at": i.created_at.isoformat() if i.created_at else "",
        }
        for i in issues
    ]


@app.get("/api/validation/catalog")
async def validation_catalog(user=Depends(get_current_user)):
    return RULE_CATALOG


@app.post("/api/validation/run")
async def run_validation(
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("approver", "unit-admin", "esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed to run validation")

    # Load all fields
    result = await db.execute(select(BrsrField))
    all_fields = result.scalars().all()

    # Scope
    if user["role"] in ("approver", "unit-admin"):
        all_fields = [f for f in all_fields if f.entity_slug == user["entity"]]

    # Wipe previously open issues (keep resolved history)
    old_result = await db.execute(
        select(ValidationIssue).where(ValidationIssue.status == "Open")
    )
    for old in old_result.scalars().all():
        await db.delete(old)
    await db.commit()

    # Run the rules
    new_issues = run_rules(all_fields)

    for issue in new_issues:
        db.add(ValidationIssue(**issue))

    await db.commit()
    return {"status": "completed", "issues_found": len(new_issues)}


@app.post("/api/validation/resolve/{issue_id}")
async def resolve_validation_issue(
    issue_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("approver", "unit-admin", "esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    issue = await db.get(ValidationIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue.status = "Resolved"
    issue.resolved_by = user["name"]
    from datetime import datetime as _dt, timezone as _tz
    issue.resolved_at = _dt.now(_tz.utc)
    db.add(issue)
    await db.commit()
    return {"status": "resolved"}

# ---------------- AUDIT TRAIL ----------------
@app.get("/api/audit/list")
async def list_audit(
    entity_slug: str = None,
    action: str = None,
    search: str = None,
    limit: int = 200,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    )
    logs = result.scalars().all()

    # Scope filter
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        logs = [l for l in logs if l.entity_slug == user["entity"]]

    # Optional entity filter (for group-level users)
    if entity_slug:
        logs = [l for l in logs if l.entity_slug == entity_slug]

    # Optional action filter
    if action:
        logs = [l for l in logs if l.action == action]

    # Optional search (matches user, datapoint, action, values)
    if search:
        s = search.lower()
        logs = [
            l
            for l in logs
            if s in (l.user_name or "").lower()
            or s in (l.user_code or "").lower()
            or s in (l.datapoint or "").lower()
            or s in (l.action or "").lower()
            or s in (l.to_value or "").lower()
        ]

    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else "",
            "user_code": l.user_code,
            "user_name": l.user_name,
            "role": l.role,
            "entity_slug": l.entity_slug,
            "datapoint": l.datapoint,
            "action": l.action,
            "from_value": l.from_value,
            "to_value": l.to_value,
        }
        for l in logs
    ]


@app.get("/api/audit/export")
async def export_audit(
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(2000)
    )
    logs = result.scalars().all()

    if user["role"] in ("data-entry", "approver", "unit-admin"):
        logs = [l for l in logs if l.entity_slug == user["entity"]]

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Timestamp", "User Code", "User Name", "Role",
        "Entity", "Datapoint", "Action", "From Value", "To Value",
    ])
    for l in logs:
        writer.writerow([
            l.timestamp.isoformat() if l.timestamp else "",
            l.user_code,
            l.user_name,
            l.role,
            l.entity_slug,
            l.datapoint,
            l.action,
            l.from_value,
            l.to_value,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="MEIL_Audit_Trail.csv"'
        },
    )

# ---------------- CHATBOT ----------------
class ChatRequest(BaseModel):
    message: str


@app.get("/api/chatbot/greet")
async def chatbot_greet(user=Depends(get_current_user)):
    return {
        "greeting": get_greeting(user["role"]),
        "suggestions": get_suggestions(user["role"]),
    }


@app.post("/api/chatbot/message")
async def chatbot_message(
    body: ChatRequest,
    user=Depends(get_current_user),
):
    answer = find_answer(body.message, user["role"])
    return {"reply": answer}

# ---------------- SECURITY ----------------
@app.post("/api/security/log-attempt")
async def log_security_attempt(
    body: SecurityLog,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    # Log as an audit entry for traceability
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=user["entity"],
        datapoint="security-screenshot-attempt",
        action="Capture Attempt",
        from_value="",
        to_value=body.method,
    ))
    await db.commit()
    return {"status": "logged"}

# ---------------- AI GAP ANALYSIS ----------------
class GapAnalysisRequest(BaseModel):
    entity_slug: str


@app.post("/api/ai/gap-analysis")
async def ai_gap_analysis(
    body: GapAnalysisRequest,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    # Group-level users can analyze any entity; others only their own
    if user["role"] in ("esg-officer", "group-admin"):
        target = body.entity_slug
    else:
        target = user["entity"]

    result = await db.execute(
        select(BrsrField).where(BrsrField.entity_slug == target)
    )
    fields = result.scalars().all()

    report = run_gap_analysis([f.dict() for f in fields], target)
    return report

# ---------------- EVIDENCE FILE MANAGEMENT ----------------
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@app.post("/api/evidence/upload")
async def upload_evidence(
    field_id: int = Form(...),
    entity_slug: str = Form(...),
    note: str = Form(""),
    file: UploadFile = File(...),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    field = await db.get(BrsrField, field_id)
    if not field or field.entity_slug != entity_slug:
        raise HTTPException(status_code=404, detail="Field not found for this entity")

    existing_result = await db.execute(
        select(Evidence)
        .where(Evidence.field_id == field_id)
        .where(Evidence.original_filename == file.filename)
    )
    existing = existing_result.scalars().all()
    version = len(existing) + 1

    if "." in file.filename:
        name_without_ext, ext = file.filename.rsplit(".", 1)
        ext = "." + ext
    else:
        name_without_ext, ext = file.filename, ""

    stored_filename = f"field_{field_id}_{name_without_ext}_v{version}{ext}"
    encoded = base64.b64encode(contents).decode("ascii")

    evidence = Evidence(
        field_id=field_id,
        entity_slug=entity_slug,
        original_filename=file.filename,
        stored_filename=stored_filename,
        version=version,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(contents),
        data_base64=encoded,
        uploaded_by_code=user["sub"],
        uploaded_by_name=user["name"],
        note=note or None,
    )
    db.add(evidence)

    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=entity_slug,
        datapoint=field.code,
        action="Evidence uploaded",
        from_value="",
        to_value=f"{file.filename} (v{version}, {len(contents)} bytes)",
    ))

    await db.commit()
    return {
        "status": "uploaded",
        "id": evidence.id,
        "original_filename": file.filename,
        "stored_filename": stored_filename,
        "version": version,
        "size_bytes": len(contents),
    }


@app.get("/api/evidence/field/{field_id}")
async def list_evidence_for_field(
    field_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Evidence)
        .where(Evidence.field_id == field_id)
        .order_by(Evidence.uploaded_at.desc())
    )
    items = result.scalars().all()
    return [
        {
            "id": e.id,
            "field_id": e.field_id,
            "original_filename": e.original_filename,
            "stored_filename": e.stored_filename,
            "version": e.version,
            "content_type": e.content_type,
            "size_bytes": e.size_bytes,
            "uploaded_by_code": e.uploaded_by_code,
            "uploaded_by_name": e.uploaded_by_name,
            "uploaded_at": e.uploaded_at.isoformat() if e.uploaded_at else "",
            "note": e.note,
        }
        for e in items
    ]


@app.get("/api/evidence/download/{evidence_id}")
async def download_evidence(
    evidence_id: int,
    db=Depends(get_db),
):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    data = base64.b64decode(evidence.data_base64)
    return Response(
        content=data,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.stored_filename}"'
        },
    )


@app.delete("/api/evidence/{evidence_id}")
async def delete_evidence(
    evidence_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    can_delete = (
        evidence.uploaded_by_code == user["sub"]
        or user["role"] in ("unit-admin", "esg-officer", "group-admin")
    )
    if not can_delete:
        raise HTTPException(status_code=403, detail="Not allowed to delete this file")

    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=evidence.entity_slug,
        datapoint=f"field_{evidence.field_id}",
        action="Evidence deleted",
        from_value=f"{evidence.original_filename} (v{evidence.version})",
        to_value="",
    ))
    await db.delete(evidence)
    await db.commit()
    return {"status": "deleted"}

# ---------------- CARBON CALCULATOR ----------------
class ElectricityCalcRequest(BaseModel):
    kwh: float


class FuelCalcRequest(BaseModel):
    fuel_type: str
    quantity: float


class UnitConvertRequest(BaseModel):
    value: float
    from_unit: str
    to_unit: str


@app.get("/api/carbon/reference")
async def carbon_reference(user=Depends(get_current_user)):
    """Returns the full reference table of emission factors."""
    return get_all_reference_data()


@app.post("/api/carbon/calc/electricity")
async def carbon_calc_electricity(
    body: ElectricityCalcRequest,
    user=Depends(get_current_user),
):
    """Convert kWh to tCO2e using the Indian grid emission factor."""
    return calc_electricity_emissions(body.kwh)


@app.post("/api/carbon/calc/fuel")
async def carbon_calc_fuel(
    body: FuelCalcRequest,
    user=Depends(get_current_user),
):
    """Convert fuel consumption to tCO2e."""
    return calc_fuel_emissions(body.fuel_type, body.quantity)


@app.post("/api/carbon/calc/renewable")
async def carbon_calc_renewable(
    body: ElectricityCalcRequest,
    user=Depends(get_current_user),
):
    """Calculate emissions avoided by using renewable electricity."""
    return calc_renewable_offset(body.kwh)


@app.post("/api/carbon/convert")
async def carbon_convert(
    body: UnitConvertRequest,
    user=Depends(get_current_user),
):
    """Generic unit converter (kWh↔GJ, L↔tonne, etc.)."""
    return convert_units(body.value, body.from_unit, body.to_unit)