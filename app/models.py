from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone


class Entity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str
    type: str
    parent_slug: Optional[str] = None
    progress: float = 0.0
    code: str


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    role: str
    entity_slug: str
    name: str
    initials: str
    password_hash: str


class BrsrSection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    name: str
    sub: str
    owner: str


class BrsrField(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    section_code: str
    entity_slug: str
    code: str
    label: str
    field_type: str = "text"
    unit: Optional[str] = None
    required: bool = True
    value: str = ""
    status: str = "pending"
    warn: Optional[str] = None


class Submission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: str = Field(unique=True)
    entity_slug: str
    section_code: str
    state: str
    submitted_by: str
    approver: Optional[str] = None
    remarks: str = ""


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_code: str
    user_name: str
    role: str
    entity_slug: str
    datapoint: str
    action: str
    from_value: str = ""
    to_value: str = ""



class Attachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    field_id: int = Field(index=True)
    entity_slug: str
    section_code: str
    field_code: str
    filename: str
    stored_name: str
    content_type: str
    size: int
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))