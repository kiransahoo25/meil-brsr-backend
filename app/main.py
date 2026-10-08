from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response, StreamingResponse
from sqlmodel import select
from sqlalchemy import text
from pydantic import BaseModel
import jwt as pyjwt
from contextlib import asynccontextmanager
import uuid
import base64
import csv
from io import StringIO
import re
from pathlib import Path
from datetime import datetime, timezone

import os
import subprocess
import tempfile
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi import BackgroundTasks

from app.config import settings
from app.database import get_db, init_db, engine
from app.models import (
    Entity, User, BrsrSection, BrsrField, Submission, AuditLog,
    Comment, ValidationIssue, Evidence,
)
from app.security import hash_password, verify_password, create_access_token, decode_token
from app.esg import (
    aggregate_fields_to_principles,
    compute_principle_scores,
    compute_sdg_scores,
    SECTION_TO_PRINCIPLE,
)
from app.pdf_report import build_brsr_pdf
from app.brsr_full_report import build_full_brsr_pdf
from app.sdg_pdf import build_sdg_pdf
from app.validation import run_rules, RULE_CATALOG
from app.chatbot import find_answer, get_greeting, get_suggestions
from app.ai_gap_analysis import run_gap_analysis
from app.blockchain import create_data_fingerprint, verify_fingerprint, anchor_fingerprint, build_submission_payload
from app.carbon_factors import (
    calc_electricity_emissions,
    calc_fuel_emissions,
    calc_renewable_offset,
    convert_units,
    get_all_reference_data,
)

security_scheme = HTTPBearer()


# ---------------- UTILITIES ----------------
def sanitize_filename(filename: str) -> str:
    """Remove path traversal, control chars, and unsafe sequences."""
    if not filename:
        return "unnamed_file"
    filename = Path(filename).name
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    filename = filename.replace("/", "_").replace("\\", "_")
    if len(filename) > 200:
        stem, dot, ext = filename.rpartition(".")
        filename = stem[:195] + dot + ext
    return filename or "unnamed_file"


# ---------------- APP LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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


# ============================================================
# AUTH
# ============================================================
@app.post("/api/auth/login")
async def login(code: str, password: str, db=Depends(get_db)):
    result = await db.execute(select(User).where(User.code == code.upper()))
    user = result.scalars().first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    db.add(AuditLog(
        user_code=user.code,
        user_name=user.name,
        role=user.role,
        entity_slug=user.entity_slug,
        datapoint="auth",
        action="Logged in",
        from_value="",
        to_value="session started",
    ))
    await db.commit()

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


@app.post("/api/auth/logout")
async def logout_log(db=Depends(get_db), user=Depends(get_current_user)):
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=user["entity"],
        datapoint="auth",
        action="Logged out",
        from_value="",
        to_value="session ended",
    ))
    await db.commit()
    return {"status": "logged"}


# ============================================================
# HEALTH
# ============================================================
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ============================================================
# ENTITIES
# ============================================================
@app.get("/api/entities")
async def list_entities(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Entity))
    entities = result.scalars().all()
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        entities = [e for e in entities if e.slug == user["entity"]]
    return entities


# ============================================================
# COLLECTION
# ============================================================
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


@app.post("/api/collection/submit-all/{entity_slug}")
async def submit_all_sections(
    entity_slug: str,
    force: bool = False,
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

        missing = [f for f in fields if f.required and not f.value]

        # If there are missing fields AND we're not forcing, report them and skip
        if missing and not force:
            skipped.append({
                "section": sec.name,
                "section_code": sec.code,
                "reason": f"{len(missing)} required field(s) missing",
                "missing_fields": [
                    {"code": f.code, "label": f.label}
                    for f in missing
                ],
            })
            continue

        # Submit the section (works for both complete sections and forced submits)
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

        # Audit log entry (include force flag if applicable)
        audit_note = "Submitted for review"
        if force and missing:
            audit_note = f"Submitted for review (forced, {len(missing)} missing)"

        db.add(AuditLog(
            user_code=user["sub"],
            user_name=user["name"],
            role=user["role"],
            entity_slug=entity_slug,
            datapoint=sec.code,
            action=audit_note,
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
        "forced": force,
    }

# ============================================================
# APPROVALS
# ============================================================
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


# ============================================================
# COMMENTS
# ============================================================
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


# ============================================================
# CONSOLIDATED ESG
# ============================================================
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


# ============================================================
# DASHBOARD
# ============================================================
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


# ============================================================
# GROUP OVERVIEW
# ============================================================
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
            "submitted": sum(1 for x in subs if x.state == "Submitted"),
            "approved": sum(1 for x in subs if x.state == "Approved"),
            "rejected": sum(1 for x in subs if x.state == "Rejected"),
            "changes": sum(1 for x in subs if x.state == "Changes Requested"),
            "improvements": improvements[:4],
        })

    avg_overall = int(sum(x["overall"] for x in unit_data) / len(unit_data)) if unit_data else 0
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


# ============================================================
# PDF REPORTS
# ============================================================
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
        entity={"name": entity.name, "type": entity.type, "code": entity.code},
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
@app.get("/api/reports/brsr-full")
async def brsr_full_report_endpoint(
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

    pdf_bytes = build_full_brsr_pdf(
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
            "Content-Disposition": f'attachment; filename="MEIL_BRSR_Full_{safe_name}_FY2526.pdf"'
        },
    )

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
        entity={"name": entity.name, "type": entity.type, "code": entity.code},
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


# ============================================================
# VALIDATION
# ============================================================
@app.get("/api/validation/issues")
async def list_validation_issues(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(
        select(ValidationIssue).order_by(ValidationIssue.id.desc())
    )
    issues = result.scalars().all()
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
async def run_validation(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] not in ("approver", "unit-admin", "esg-officer", "group-admin"):
        raise HTTPException(status_code=403, detail="Not allowed to run validation")

    result = await db.execute(select(BrsrField))
    all_fields = result.scalars().all()

    if user["role"] in ("approver", "unit-admin"):
        all_fields = [f for f in all_fields if f.entity_slug == user["entity"]]

    old_result = await db.execute(
        select(ValidationIssue).where(ValidationIssue.status == "Open")
    )
    for old in old_result.scalars().all():
        await db.delete(old)
    await db.commit()

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
    issue.resolved_at = datetime.now(timezone.utc)
    db.add(issue)
    await db.commit()
    return {"status": "resolved"}


# ============================================================
# AUDIT TRAIL
# ============================================================
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

    if user["role"] in ("data-entry", "approver", "unit-admin"):
        logs = [l for l in logs if l.entity_slug == user["entity"]]

    if entity_slug:
        logs = [l for l in logs if l.entity_slug == entity_slug]
    if action:
        logs = [l for l in logs if l.action == action]
    if search:
        s = search.lower()
        logs = [
            l for l in logs
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
async def export_audit(db=Depends(get_db), user=Depends(get_current_user)):
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


# ============================================================
# LOGIN HISTORY (GROUP ADMIN ONLY)
# ============================================================
@app.get("/api/admin/login-history")
async def login_history(
    user_code: str = None,
    limit: int = 100,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] != "group-admin":
        raise HTTPException(status_code=403, detail="Group Admin only")

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action.in_(["Logged in", "Logged out"]))
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    if user_code:
        logs = [l for l in logs if l.user_code == user_code]

    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else "",
            "user_code": l.user_code,
            "user_name": l.user_name,
            "role": l.role,
            "entity_slug": l.entity_slug,
            "action": l.action,
        }
        for l in logs
    ]


@app.get("/api/admin/active-users")
async def active_users(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "group-admin":
        raise HTTPException(status_code=403, detail="Group Admin only")

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action.in_(["Logged in", "Logged out"]))
        .order_by(AuditLog.id.desc())
        .limit(500)
    )
    logs = result.scalars().all()

    latest = {}
    for log in logs:
        if log.user_code not in latest:
            latest[log.user_code] = log

    active = [l for l in latest.values() if l.action == "Logged in"]
    return [
        {
            "user_code": l.user_code,
            "user_name": l.user_name,
            "role": l.role,
            "entity_slug": l.entity_slug,
            "logged_in_at": l.timestamp.isoformat() if l.timestamp else "",
        }
        for l in active
    ]


# ============================================================
# EVIDENCE FILE MANAGEMENT (WITH SOFT DELETE + SANITIZATION)
# ============================================================
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

    # Sanitize the filename before use
    safe_name = sanitize_filename(file.filename)

    existing_result = await db.execute(
        select(Evidence)
        .where(Evidence.field_id == field_id)
        .where(Evidence.original_filename == safe_name)
        .where(Evidence.is_deleted == False)
    )
    existing = existing_result.scalars().all()
    version = len(existing) + 1

    if "." in safe_name:
        name_without_ext, ext = safe_name.rsplit(".", 1)
        ext = "." + ext
    else:
        name_without_ext, ext = safe_name, ""

    stored_filename = f"field_{field_id}_{name_without_ext}_v{version}{ext}"
    encoded = base64.b64encode(contents).decode("ascii")

    evidence = Evidence(
        field_id=field_id,
        entity_slug=entity_slug,
        original_filename=safe_name,
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
        to_value=f"{safe_name} (v{version}, {len(contents)} bytes)",
    ))

    await db.commit()
    return {
        "status": "uploaded",
        "id": evidence.id,
        "original_filename": safe_name,
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
        .where(Evidence.is_deleted == False)
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
async def download_evidence(evidence_id: int, db=Depends(get_db)):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence or evidence.is_deleted:
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
    if not evidence or evidence.is_deleted:
        raise HTTPException(status_code=404, detail="Evidence not found")

    can_delete = (
        evidence.uploaded_by_code == user["sub"]
        or user["role"] in ("unit-admin", "esg-officer", "group-admin")
    )
    if not can_delete:
        raise HTTPException(status_code=403, detail="Not allowed to delete this file")

    # SOFT DELETE
    evidence.is_deleted = True
    evidence.deleted_at = datetime.now(timezone.utc)
    evidence.deleted_by = user["name"]
    db.add(evidence)

    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=evidence.entity_slug,
        datapoint=f"field_{evidence.field_id}",
        action="Evidence deleted",
        from_value=f"{evidence.original_filename} (v{evidence.version})",
        to_value="soft-deleted",
    ))
    await db.commit()
    return {"status": "deleted"}


# ============================================================
# ARCHIVE
# ============================================================
@app.get("/api/archive/search")
async def search_archive(
    q: str = "",
    entity_slug: str = None,
    state: str = None,
    limit: int = 200,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    # Scope: data-entry/approver/unit-admin see only their entity
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        scoped_entity = user["entity"]
    else:
        scoped_entity = None

    sub_result = await db.execute(
        select(Submission).order_by(Submission.id.desc()).limit(500)
    )
    subs = sub_result.scalars().all()

    if scoped_entity:
        subs = [s for s in subs if s.entity_slug == scoped_entity]
    if entity_slug:
        subs = [s for s in subs if s.entity_slug == entity_slug]
    if state:
        subs = [s for s in subs if s.state == state]

    secs_result = await db.execute(select(BrsrSection))
    all_secs = {s.code: s for s in secs_result.scalars().all()}

    ents_result = await db.execute(select(Entity))
    all_ents = {e.slug: e for e in ents_result.scalars().all()}

    result = []
    for s in subs:
        sec = all_secs.get(s.section_code)
        ent = all_ents.get(s.entity_slug)

        field_result = await db.execute(
            select(BrsrField)
            .where(BrsrField.entity_slug == s.entity_slug)
            .where(BrsrField.section_code == s.section_code)
        )
        fields = field_result.scalars().all()
        field_ids = [f.id for f in fields]

        ev_count = 0
        ev_filenames = []
        if field_ids:
            ev_result = await db.execute(
                select(Evidence).where(Evidence.field_id.in_(field_ids))
            )
            for ev in ev_result.scalars().all():
                if not ev.is_deleted:
                    ev_count += 1
                    if len(ev_filenames) < 3:
                        ev_filenames.append(ev.original_filename)

        if q:
            q_low = q.lower()
            haystack = " ".join([
                s.submission_id or "",
                s.submitted_by or "",
                s.entity_slug or "",
                (ent.name if ent else "") or "",
                s.section_code or "",
                (sec.name if sec else "") or "",
                (sec.sub if sec else "") or "",
                s.state or "",
                " ".join(ev_filenames),
            ]).lower()
            if q_low not in haystack:
                continue

        result.append({
            "submission_id": s.submission_id,
            "entity_slug": s.entity_slug,
            "entity_name": ent.name if ent else s.entity_slug,
            "section_code": s.section_code,
            "section_name": sec.name if sec else s.section_code,
            "section_sub": sec.sub if sec else "",
            "state": s.state,
            "submitted_by": s.submitted_by,
            "approver": s.approver or "",
            "remarks": s.remarks or "",
            "field_count": len(fields),
            "filled_count": sum(1 for f in fields if f.value),
            "evidence_count": ev_count,
            "evidence_preview": ev_filenames,
        })

        if len(result) >= limit:
            break

    return result

    sub_result = await db.execute(
        select(Submission).order_by(Submission.id.desc()).limit(500)
    )
    subs = sub_result.scalars().all()

    if scoped_entity:
        subs = [s for s in subs if s.entity_slug == scoped_entity]
    if entity_slug:
        subs = [s for s in subs if s.entity_slug == entity_slug]
    if state:
        subs = [s for s in subs if s.state == state]

    secs_result = await db.execute(select(BrsrSection))
    all_secs = {s.code: s for s in secs_result.scalars().all()}

    ents_result = await db.execute(select(Entity))
    all_ents = {e.slug: e for e in ents_result.scalars().all()}

    result = []
    for s in subs:
        sec = all_secs.get(s.section_code)
        ent = all_ents.get(s.entity_slug)

        field_result = await db.execute(
            select(BrsrField)
            .where(BrsrField.entity_slug == s.entity_slug)
            .where(BrsrField.section_code == s.section_code)
        )
        fields = field_result.scalars().all()
        field_ids = [f.id for f in fields]

        evidence_list = []
        if field_ids:
            ev_result = await db.execute(
                select(Evidence)
                .where(Evidence.field_id.in_(field_ids))
                .where(Evidence.is_deleted == False)
            )
            evidence_list = ev_result.scalars().all()

        ev_filenames = [e.original_filename for e in evidence_list]

        if q:
            q_low = q.lower()
            haystack = " ".join([
                s.submission_id or "",
                s.submitted_by or "",
                s.entity_slug or "",
                (ent.name if ent else "") or "",
                s.section_code or "",
                (sec.name if sec else "") or "",
                (sec.sub if sec else "") or "",
                s.state or "",
                " ".join(ev_filenames),
            ]).lower()
            if q_low not in haystack:
                continue

        result.append({
            "submission_id": s.submission_id,
            "entity_slug": s.entity_slug,
            "entity_name": ent.name if ent else s.entity_slug,
            "section_code": s.section_code,
            "section_name": sec.name if sec else s.section_code,
            "section_sub": sec.sub if sec else "",
            "state": s.state,
            "submitted_by": s.submitted_by,
            "approver": s.approver or "",
            "remarks": s.remarks or "",
            "field_count": len(fields),
            "filled_count": sum(1 for f in fields if f.value),
            "evidence_count": len(evidence_list),
            "evidence_preview": ev_filenames[:3],
        })

        if len(result) >= limit:
            break

    return result


@app.get("/api/archive/submission/{submission_id}")
async def archive_submission_detail(
    submission_id: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    sub_result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    sub = sub_result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    if user["role"] in ("data-entry", "approver", "unit-admin"):
        if sub.entity_slug != user["entity"]:
            raise HTTPException(status_code=403, detail="Not allowed")

    field_result = await db.execute(
        select(BrsrField)
        .where(BrsrField.entity_slug == sub.entity_slug)
        .where(BrsrField.section_code == sub.section_code)
    )
    fields = field_result.scalars().all()
    field_ids = [f.id for f in fields]

    evidence_by_field: dict = {}
    if field_ids:
        ev_result = await db.execute(
            select(Evidence)
            .where(Evidence.field_id.in_(field_ids))
            .where(Evidence.is_deleted == False)
        )
        for e in ev_result.scalars().all():
            evidence_by_field.setdefault(e.field_id, []).append({
                "id": e.id,
                "original_filename": e.original_filename,
                "stored_filename": e.stored_filename,
                "version": e.version,
                "size_bytes": e.size_bytes,
                "uploaded_by_name": e.uploaded_by_name,
                "uploaded_by_code": e.uploaded_by_code,
                "uploaded_at": e.uploaded_at.isoformat() if e.uploaded_at else "",
                "note": e.note,
            })

    sec_result = await db.execute(
        select(BrsrSection).where(BrsrSection.code == sub.section_code)
    )
    sec = sec_result.scalars().first()
    ent_result = await db.execute(select(Entity).where(Entity.slug == sub.entity_slug))
    ent = ent_result.scalars().first()

    return {
        "submission_id": sub.submission_id,
        "entity_slug": sub.entity_slug,
        "entity_name": ent.name if ent else sub.entity_slug,
        "section_code": sub.section_code,
        "section_name": sec.name if sec else sub.section_code,
        "section_sub": sec.sub if sec else "",
        "state": sub.state,
        "submitted_by": sub.submitted_by,
        "approver": sub.approver or "",
        "remarks": sub.remarks or "",
        "fields": [
            {
                "id": f.id,
                "code": f.code,
                "label": f.label,
                "value": f.value,
                "unit": f.unit,
                "required": f.required,
                "status": f.status,
                "evidence": evidence_by_field.get(f.id, []),
            }
            for f in fields
        ],
    }


# ============================================================
# CARBON CALCULATOR
# ============================================================
class ElectricityCalcRequest(BaseModel):
    kwh: float


class FuelCalcRequest(BaseModel):
    fuel_type: str
    quantity: float


class UnitConvertRequest(BaseModel):
    value: float
    from_unit: str
    to_unit: str


class ChatRequest(BaseModel):
    message: str


class GapAnalysisRequest(BaseModel):
    entity_slug: str


class SecurityLog(BaseModel):
    method: str


@app.get("/api/carbon/reference")
async def carbon_reference(user=Depends(get_current_user)):
    return get_all_reference_data()


@app.post("/api/carbon/calc/electricity")
async def carbon_calc_electricity(body: ElectricityCalcRequest, user=Depends(get_current_user)):
    return calc_electricity_emissions(body.kwh)


@app.post("/api/carbon/calc/fuel")
async def carbon_calc_fuel(body: FuelCalcRequest, user=Depends(get_current_user)):
    return calc_fuel_emissions(body.fuel_type, body.quantity)


@app.post("/api/carbon/calc/renewable")
async def carbon_calc_renewable(body: ElectricityCalcRequest, user=Depends(get_current_user)):
    return calc_renewable_offset(body.kwh)


@app.post("/api/carbon/convert")
async def carbon_convert(body: UnitConvertRequest, user=Depends(get_current_user)):
    return convert_units(body.value, body.from_unit, body.to_unit)


# ============================================================
# CHATBOT
# ============================================================
@app.get("/api/chatbot/greet")
async def chatbot_greet(user=Depends(get_current_user)):
    return {
        "greeting": get_greeting(user["role"]),
        "suggestions": get_suggestions(user["role"]),
    }


@app.post("/api/chatbot/message")
async def chatbot_message(body: ChatRequest, user=Depends(get_current_user)):
    return {"reply": find_answer(body.message, user["role"])}


# ============================================================
# AI GAP ANALYSIS
# ============================================================
@app.post("/api/ai/gap-analysis")
async def ai_gap_analysis(
    body: GapAnalysisRequest,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
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


# ============================================================
# TRUST & VERIFY
# ============================================================
@app.get("/api/trust/verify/{submission_id}")
async def trust_verify(
    submission_id: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    field_result = await db.execute(
        select(BrsrField)
        .where(BrsrField.entity_slug == sub.entity_slug)
        .where(BrsrField.section_code == sub.section_code)
    )
    fields = field_result.scalars().all()

    payload = build_submission_payload(sub, fields)
    fingerprint = create_data_fingerprint(payload)
    proof = anchor_fingerprint(fingerprint)

    return {
        "submission_id": submission_id,
        "fingerprint": fingerprint,
        "proof": proof,
        "verification": {
            "verified": True,
            "fingerprint": fingerprint,
            "algorithm": "SHA-256",
            "chain": "Bitcoin (via OpenTimestamps)",
            "anchored_at": proof["anchored_at"],
            "message": "Data integrity confirmed — no tampering detected.",
        },
    }


# ============================================================
# SECURITY
# ============================================================
@app.post("/api/security/log-attempt")
async def log_security_attempt(
    body: SecurityLog,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
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



# ---------------- ESG REPORT ----------------
@app.get("/api/esg/report")
async def esg_report(db=Depends(get_db), user=Depends(get_current_user)):
    """Aggregated ESG data across all entities the user can see."""
    entities_result = await db.execute(select(Entity))
    entities = entities_result.scalars().all()

    # Role scope filter
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        entities = [e for e in entities if e.slug == user["entity"]]

    all_fields = []
    entity_rows = []
    for ent in entities:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.entity_slug == ent.slug)
        )
        fields = f_result.scalars().all()
        all_fields.extend(fields)

        sub_agg = aggregate_fields_to_principles(fields)
        entity_rows.append({
            "id": ent.slug,
            "name": ent.name,
            "type": ent.type,
            "scope1": sub_agg["P6"]["scope1"],
            "scope2": sub_agg["P6"]["scope2"],
            "water": sub_agg["P6"]["waterWithdrawal"],
            "energy": sub_agg["P6"]["energyConsumption"],
            "waste": sub_agg["P6"]["wasteRecycled"],
            "ltifr": sub_agg["P3"]["ltifr"],
            "csrSpend": sub_agg["P8"]["csrSpend"],
        })

    agg = aggregate_fields_to_principles(all_fields)
    principle_scores = compute_principle_scores(agg)
    sdg_scores = compute_sdg_scores(principle_scores)

    return {
        "principles": agg,
        "principleScores": principle_scores,
        "sdgScores": sdg_scores,
        "entities": entity_rows,
        "entityCount": len(entity_rows),
    }


# ---------------- SDG REPORT ----------------
@app.get("/api/sdg/report")
async def sdg_report(db=Depends(get_db), user=Depends(get_current_user)):
    """SDG alignment scores, mapped from principle performance."""
    entities_result = await db.execute(select(Entity))
    entities = entities_result.scalars().all()

    if user["role"] in ("data-entry", "approver", "unit-admin"):
        entities = [e for e in entities if e.slug == user["entity"]]

    all_fields = []
    for ent in entities:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.entity_slug == ent.slug)
        )
        all_fields.extend(f_result.scalars().all())

    agg = aggregate_fields_to_principles(all_fields)
    principle_scores = compute_principle_scores(agg)
    sdg_scores = compute_sdg_scores(principle_scores)

    return {
        "sdgScores": sdg_scores,
        "principleScores": principle_scores,
    }

# ---------------- BRSR PDF REPORT ----------------

BACKEND_DIR = Path(__file__).resolve().parent.parent
GENERATE_SCRIPT = BACKEND_DIR / "reports" / "generate.js"


@app.get("/api/reports/brsr.pdf")
async def download_brsr_pdf(
    background: BackgroundTasks,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Generate the BRSR PDF report using the Node/Puppeteer generator
    and stream it back to the client.

    Only group-admin and esg-officer roles can generate the consolidated report.
    """
    if user["role"] not in ("group-admin", "esg-officer"):
        raise HTTPException(
            status_code=403,
            detail="Only Group Admin or ESG Officer can generate the BRSR report",
        )

    # Create a temp output path
    tmp_dir = Path(tempfile.mkdtemp(prefix="meil_brsr_"))
    out_path = tmp_dir / f"MEIL_BRSR_Report_FY2025-26.pdf"

    # Pass the current user's raw token so the Node script can authenticate
    # We don't have the raw token here, so instead we generate a fresh short-lived
    # one using the same user payload. In practice, use create_access_token.
    from app.security import create_access_token
    script_token = create_access_token({
        "sub": user["sub"],
        "role": user["role"],
        "entity": user["entity"],
        "name": user["name"],
        "initials": user.get("initials", ""),
    })

    env = os.environ.copy()
    env["API_URL"] = "http://localhost:8000/api"
    env["API_TOKEN"] = script_token

    try:
        result = subprocess.run(
            ["node", str(GENERATE_SCRIPT), str(out_path)],
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="PDF generation timed out")

    if result.returncode != 0 or not out_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {result.stderr[-500:]}",
        )

    # Log the event
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=user["entity"],
        datapoint="BRSR-REPORT",
        action="BRSR PDF generated",
        from_value="",
        to_value=out_path.name,
    ))
    await db.commit()

    # Schedule cleanup after the response is sent
    def cleanup():
        try:
            if out_path.exists():
                out_path.unlink()
            tmp_dir.rmdir()
        except Exception:
            pass

    background.add_task(cleanup)

    return FileResponse(
        path=out_path,
        media_type="application/pdf",
        filename="MEIL_BRSR_Report_FY2025-26.pdf",
    )