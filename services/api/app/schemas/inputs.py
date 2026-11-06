from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Register(Input):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    organization: str = Field(min_length=2, max_length=120)


class Login(Input):
    email: EmailStr
    password: str = Field(max_length=128)


class CustomerInput(Input):
    name: str = Field(min_length=2, max_length=160)
    company: str = Field(default='', max_length=160)
    email: str = Field(default='', max_length=254, pattern=r'^$|^[^\s@]+@[^\s@]+\.[^\s@]+$')
    phone: str = Field(default='', max_length=60)
    stage: Literal['lead', 'qualified', 'active', 'at_risk', 'closed'] = 'lead'
    tags: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default='', max_length=20000)
    owner: str = Field(default='', max_length=100)
    opted_out: bool = False


class WorkflowInput(Input):
    title: str = Field(min_length=3, max_length=200)
    request: str = Field(min_length=10, max_length=20000)
    customer_id: str | None = None
    priority: Literal['low', 'medium', 'high', 'urgent'] = 'medium'
    due_at: datetime | None = None
    room_id: str = Field(default='', max_length=200)


class RecordInput(Input):
    title: str = Field(min_length=1, max_length=200)
    status: str = Field(default='open', max_length=30)
    data: dict = Field(default_factory=dict)


class Decision(Input):
    decision: Literal['APPROVED', 'REJECTED', 'CHANGES_REQUESTED']
    reason: str = Field(default='', max_length=4000)


class IntegrationInput(Input):
    config: dict
    secret: str | None = Field(default=None, max_length=16000)


class DocumentEdit(Input):
    content: str = Field(min_length=10, max_length=100000)
