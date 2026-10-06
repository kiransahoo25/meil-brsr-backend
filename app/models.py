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


class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: str
    author_code: str
    author_name: str
    author_role: str
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_slug: str
    section_code: str
    datapoint: str
    field_label: str
    severity: str  # High | Medium | Low
    rule_name: str
    message: str
    status: str = "Open"  # Open | Resolved
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Evidence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    field_id: int = Field(index=True)
    entity_slug: str
    original_filename: str
    stored_filename: str
    version: int = 1
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    data_base64: str
    uploaded_by_code: str
    uploaded_by_name: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: Optional[str] = None
        # Soft delete fields
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None