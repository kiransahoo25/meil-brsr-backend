from fastapi import UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
import jwt as pyjwt
from contextlib import asynccontextmanager
import uuid

from app.config import settings
from app.database import get_db, init_db, engine
from app.models import Entity, User, BrsrSection, BrsrField, Submission, AuditLog , Attachment
from app.security import hash_password, verify_password, create_access_token, decode_token
from app.esg import (
    aggregate_fields_to_principles,
    compute_principle_scores,
    compute_sdg_scores,
    SECTION_TO_PRINCIPLE,
)
security_scheme = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(title="MEIL BRSR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"],
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


# ---------------- DASHBOARD ----------------
@app.get("/api/dashboard/stats")
async def dashboard_stats(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(BrsrSection))
    sections = result.scalars().all()

    section_progress = []
    for s in sections:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.section_code == s.code)
        )
        fields = f_result.scalars().all()
        done = sum(1 for f in fields if f.status == "complete")
        pct = int((done / len(fields)) * 100) if fields else 0
        section_progress.append({
            "code": s.code,
            "name": s.name,
            "sub": s.sub,
            "progress": pct,
        })

    sub_result = await db.execute(select(Submission))
    subs = sub_result.scalars().all()

    overall = (
        sum(s["progress"] for s in section_progress) // max(len(section_progress), 1)
        if section_progress
        else 0
    )

    return {
        "overallProgress": overall,
        "openIssues": 0,
        "highSeverity": 0,
        "pendingApprovals": sum(1 for s in subs if s.state == "Submitted"),
        "assuranceReady": 0,
        "sectionProgress": section_progress,
        "recentActivity": [
            {"title": "Portal initialised", "subtitle": "System · Today"},
        ],
    }
	
	# ---------------- APPROVALS ----------------
@app.get("/api/approvals/list")
async def list_approvals(db=Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Submission))
    subs = result.scalars().all()

    # Scope filter
    if user["role"] in ("approver", "unit-admin"):
        subs = [s for s in subs if s.entity_slug == user["entity"]]

    # Enrich with section names
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


# ---------------- ESG REPORT ----------------
@app.get("/api/esg/report")
async def esg_report(db=Depends(get_db), user=Depends(get_current_user)):
    """
    Returns aggregated ESG data across all entities the user can see.
    Restricted by role: data-entry/approver/unit-admin see only their entity.
    """
    entities_result = await db.execute(select(Entity))
    entities = entities_result.scalars().all()

    # Role scope filter
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        entities = [e for e in entities if e.slug == user["entity"]]

    # Collect all fields for those entities
    all_fields = []
    entity_rows = []
    for ent in entities:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.entity_slug == ent.slug)
        )
        fields = f_result.scalars().all()
        all_fields.extend(fields)

        # Per-entity totals
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
    """
    Returns SDG alignment scores, mapped from principle performance.
    """
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


# ---------------- VALIDATION ISSUES ----------------
@app.get("/api/validation/issues")
async def validation_issues(db=Depends(get_db), user=Depends(get_current_user)):
    """
    Returns list of missing/flagged required datapoints for the user's scope.
    """
    entities_result = await db.execute(select(Entity))
    entities = entities_result.scalars().all()
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        entities = [e for e in entities if e.slug == user["entity"]]

    # All sections for labels
    sec_result = await db.execute(select(BrsrSection))
    sections = sec_result.scalars().all()
    sec_map = {s.code: s for s in sections}

    issues = []
    for ent in entities:
        f_result = await db.execute(
            select(BrsrField).where(BrsrField.entity_slug == ent.slug)
        )
        fields = f_result.scalars().all()
        for f in fields:
            if not f.required:
                continue
            missing = not f.value or str(f.value).strip() == ""
            flagged = f.status == "flagged"
            if not (missing or flagged):
                continue
            sec = sec_map.get(f.section_code)
            issues.append({
                "id": f"{f.section_code}-{f.id}",
                "entity": ent.slug,
                "entityName": ent.name,
                "section": sec.name if sec else f.section_code,
                "sectionCode": f.section_code,
                "field": f.label,
                "code": f.code,
                "severity": "high" if flagged else "medium",
                "issueType": "Flagged value" if flagged else "Missing value",
                "status": f.status,
            })

    return {
        "issues": issues,
        "totalIssues": len(issues),
        "high": sum(1 for i in issues if i["severity"] == "high"),
        "medium": sum(1 for i in issues if i["severity"] == "medium"),
    }


# ---------------- AUDIT LOG ----------------
@app.get("/api/audit/list")
async def list_audit(db=Depends(get_db), user=Depends(get_current_user)):
    """Return audit log entries, scoped by role."""
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(500)
    )
    logs = result.scalars().all()

    # Scope filter
    if user["role"] in ("data-entry", "approver", "unit-admin"):
        logs = [l for l in logs if l.entity_slug == user["entity"]]

    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "user_code": l.user_code,
            "user_name": l.user_name,
            "role": l.role,
            "entity_slug": l.entity_slug,
            "datapoint": l.datapoint,
            "action": l.action,
            "from_value": l.from_value or "",
            "to_value": l.to_value or "",
        }
        for l in logs
    ]



# ---------------- ATTACHMENTS ----------------
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.post("/api/attachments/upload/{field_id}")
async def upload_attachment(
    field_id: int,
    file: UploadFile = File(...),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("data-entry", "unit-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    field = await db.get(BrsrField, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    # Generate a safe unique filename
    import uuid
    ext = Path(file.filename).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / stored_name

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    size = dest.stat().st_size

    att = Attachment(
        field_id=field_id,
        entity_slug=field.entity_slug,
        section_code=field.section_code,
        field_code=field.code,
        filename=file.filename,
        stored_name=stored_name,
        content_type=file.content_type or "application/octet-stream",
        size=size,
        uploaded_by=user["name"],
    )
    db.add(att)
    db.add(AuditLog(
        user_code=user["sub"],
        user_name=user["name"],
        role=user["role"],
        entity_slug=field.entity_slug,
        datapoint=field.code,
        action="Attachment uploaded",
        from_value="",
        to_value=file.filename[:60],
    ))
    await db.commit()
    await db.refresh(att)

    return {
        "id": att.id,
        "filename": att.filename,
        "size": att.size,
        "contentType": att.content_type,
        "uploadedBy": att.uploaded_by,
        "uploadedAt": att.uploaded_at.isoformat(),
    }


@app.get("/api/attachments/field/{field_id}")
async def list_attachments(
    field_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Attachment).where(Attachment.field_id == field_id)
    )
    atts = result.scalars().all()
    return [
        {
            "id": a.id,
            "filename": a.filename,
            "size": a.size,
            "contentType": a.content_type,
            "uploadedBy": a.uploaded_by,
            "uploadedAt": a.uploaded_at.isoformat() if a.uploaded_at else None,
        }
        for a in atts
    ]


@app.get("/api/attachments/download/{att_id}")
async def download_attachment(
    att_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    att = await db.get(Attachment, att_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = UPLOAD_DIR / att.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(
        path,
        filename=att.filename,
        media_type=att.content_type,
    )


@app.delete("/api/attachments/{att_id}")
async def delete_attachment(
    att_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] not in ("data-entry", "unit-admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    att = await db.get(Attachment, att_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = UPLOAD_DIR / att.stored_name
    if path.exists():
        path.unlink()

    await db.delete(att)
    await db.commit()
    return {"status": "deleted"}

    # ---------------- ALL ENTITY FIELDS ----------------
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


    # ---------------- SUBMIT ALL SECTIONS ----------------
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