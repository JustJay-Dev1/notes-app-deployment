from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    title: str
    content: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class NoteOut(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
