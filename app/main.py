import logging
import os

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, SessionLocal, engine, get_db, wait_for_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notes-api")

app = FastAPI(title="Notes API", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    logger.info("Startup complete, database schema ensured")


@app.get("/")
def root():
    return {"service": "notes-api", "status": "running"}


@app.get("/healthz")
def healthz():
    """Liveness probe: process is up. Deliberately does not touch the DB."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness probe: can we actually serve traffic (DB reachable)?"""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}")
    return {"status": "ready"}


@app.post("/notes", response_model=schemas.NoteOut, status_code=201)
def create_note(note: schemas.NoteCreate, db: Session = Depends(get_db)):
    db_note = models.Note(title=note.title, content=note.content)
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


@app.get("/notes", response_model=list[schemas.NoteOut])
def list_notes(db: Session = Depends(get_db)):
    return db.query(models.Note).order_by(models.Note.id).all()


@app.get("/notes/{note_id}", response_model=schemas.NoteOut)
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(models.Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="note not found")
    return note


@app.put("/notes/{note_id}", response_model=schemas.NoteOut)
def update_note(note_id: int, update: schemas.NoteUpdate, db: Session = Depends(get_db)):
    note = db.get(models.Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="note not found")
    if update.title is not None:
        note.title = update.title
    if update.content is not None:
        note.content = update.content
    db.commit()
    db.refresh(note)
    return note


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(models.Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="note not found")
    db.delete(note)
    db.commit()
