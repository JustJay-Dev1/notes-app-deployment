from sqlalchemy import Column, DateTime, Integer, String, func

from database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(String(2000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
