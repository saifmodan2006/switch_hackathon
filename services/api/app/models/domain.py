from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, BigInteger, Boolean, JSON, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Organization(Identity, Base):
    __tablename__ = 'organizations'
    name: Mapped[str] = mapped_column(String(120))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Identity, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)


class Membership(Identity, Base):
    __tablename__ = 'memberships'
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    role: Mapped[str] = mapped_column(String(20), default='member')
    __table_args__ = (UniqueConstraint('org_id', 'user_id'),)


class SessionToken(Identity, Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Tenant:
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)


class Customer(Identity, Tenant, Base):
    __tablename__ = 'customers'
    name: Mapped[str] = mapped_column(String(160))
    company: Mapped[str] = mapped_column(String(160), default='')
    email: Mapped[str] = mapped_column(String(254), default='')
    phone: Mapped[str] = mapped_column(String(60), default='')
    stage: Mapped[str] = mapped_column(String(30), default='lead')
    tags: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default='')
    owner: Mapped[str] = mapped_column(String(100), default='')
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Workflow(Identity, Tenant, Base):
    __tablename__ = 'workflows'
    title: Mapped[str] = mapped_column(String(200))
    request: Mapped[str] = mapped_column(Text)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey('customers.id'))
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(30), default='CREATED', index=True)
    priority: Mapped[str] = mapped_column(String(20), default='medium')
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    room_id: Mapped[str] = mapped_column(String(200), default='')
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default='')
    handoffs: Mapped[int] = mapped_column(Integer, default=0)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}


class WorkflowEvent(Identity, Tenant, Base):
    __tablename__ = 'workflow_events'
    workflow_id: Mapped[str] = mapped_column(ForeignKey('workflows.id'), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    agent: Mapped[str] = mapped_column(String(100), default='')
    switch_event_id: Mapped[str] = mapped_column(String(200), default='')
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Agent(Identity, Tenant, Base):
    __tablename__ = 'agents'
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    switch_id: Mapped[str] = mapped_column(String(200), default='')
    participant_id: Mapped[str] = mapped_column(String(200), default='')
    encrypted_key: Mapped[str] = mapped_column(Text, default='')
    connection_id: Mapped[str] = mapped_column(String(36), default=uid)
    cursor: Mapped[int] = mapped_column(BigInteger, default=0)
    generation: Mapped[int | None] = mapped_column(BigInteger)
    rooms: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default='unconfigured')
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default='')
    model: Mapped[str] = mapped_column(String(100), default='')
    __table_args__ = (UniqueConstraint('org_id', 'slug'),)


class SwitchReceipt(Identity, Tenant, Base):
    __tablename__ = 'agent_messages'
    agent_id: Mapped[str] = mapped_column(ForeignKey('agents.id'))
    sequence: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (UniqueConstraint('agent_id', 'sequence'),)


class Approval(Identity, Tenant, Base):
    __tablename__ = 'approval_requests'
    workflow_id: Mapped[str] = mapped_column(ForeignKey('workflows.id'), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('generated_documents.id'))
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default='PENDING')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text, default='')
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(Identity, Tenant, Base):
    __tablename__ = 'generated_documents'
    workflow_id: Mapped[str] = mapped_column(ForeignKey('workflows.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    object_key: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (UniqueConstraint('workflow_id', 'version'),)


class Delivery(Identity, Tenant, Base):
    __tablename__ = 'email_deliveries'
    approval_id: Mapped[str] = mapped_column(ForeignKey('approval_requests.id'), unique=True)
    status: Mapped[str] = mapped_column(String(40), default='claimed')
    recipient: Mapped[str] = mapped_column(String(254))
    message_id: Mapped[str] = mapped_column(String(200))
    error: Mapped[str] = mapped_column(Text, default='')


class Knowledge(Identity, Tenant, Base):
    __tablename__ = 'knowledge_documents'
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='ready')
    object_key: Mapped[str] = mapped_column(Text, default='')


class Chunk(Identity, Tenant, Base):
    __tablename__ = 'document_chunks'
    document_id: Mapped[str] = mapped_column(ForeignKey('knowledge_documents.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON)


class Record(Identity, Tenant, Base):
    """Small domain resources: tasks, events, interactions, notifications and invitations."""
    __tablename__ = 'records'
    kind: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default='open')
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (Index('ix_records_tenant_kind', 'org_id', 'kind'),)


class Integration(Identity, Tenant, Base):
    __tablename__ = 'integrations'
    kind: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_secret: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (UniqueConstraint('org_id', 'kind'),)


class Audit(Identity, Tenant, Base):
    __tablename__ = 'audit_logs'
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(100), default='')
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Usage(Identity, Tenant, Base):
    __tablename__ = 'usage_records'
    workflow_id: Mapped[str] = mapped_column(ForeignKey('workflows.id'))
    agent: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class Idempotency(Identity, Tenant, Base):
    __tablename__ = 'idempotency_records'
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (UniqueConstraint('org_id', 'key'),)
