import os
from datetime import datetime, date
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./personal_life.db")
API_KEY = os.getenv("PERSONAL_API_KEY", "change-this-before-use")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Entry(Base):
    __tablename__ = "entries"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(40), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    details = Column(Text, default="")
    status = Column(String(40), default="active")
    target_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Personal Life API",
    description="A private API for tracking your goals, habits, workouts, career, projects, and journal.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # personal use: allow any frontend. Restrict to your GitHub Pages URL later if you want.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_CATEGORIES = {"goal", "habit", "workout", "job_application", "project", "journal", "skill", "note"}

def authenticate(x_api_key: Optional[str] = Header(default=None)):
    if not API_KEY or API_KEY == "change-this-before-use":
        # Allow local setup to start, but do not silently accept the default key.
        raise HTTPException(status_code=503, detail="Set PERSONAL_API_KEY to a strong secret before using the API.")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
    return True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class EntryCreate(BaseModel):
    category: str = Field(..., description="goal, habit, workout, job_application, project, journal, skill, or note")
    title: str = Field(..., min_length=1, max_length=200)
    details: str = ""
    status: str = "active"
    target_date: Optional[date] = None

class EntryUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    details: Optional[str] = None
    status: Optional[str] = None
    target_date: Optional[date] = None

class EntryOut(BaseModel):
    id: int
    category: str
    title: str
    details: str
    status: str
    target_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

@app.get("/")
def root():
    return {"name": "Personal Life API", "version": "0.1.0", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/me", dependencies=[Depends(authenticate)])
def me():
    return {
        "profile": "Personal Life API owner",
        "purpose": "Private, user-controlled life data",
        "domains": sorted(ALLOWED_CATEGORIES),
        "note": "Edit this endpoint to add only the profile fields you actually want stored."
    }

@app.post("/api/v1/entries", response_model=EntryOut, dependencies=[Depends(authenticate)], status_code=201)
def create_entry(payload: EntryCreate, db: Session = Depends(get_db)):
    category = payload.category.strip().lower()
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}")
    row = Entry(category=category, title=payload.title.strip(), details=payload.details,
                status=payload.status, target_date=payload.target_date)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.get("/api/v1/entries", response_model=list[EntryOut], dependencies=[Depends(authenticate)])
def list_entries(
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Entry)
    if category:
        query = query.filter(Entry.category == category.strip().lower())
    if status:
        query = query.filter(Entry.status == status)
    return query.order_by(Entry.created_at.desc()).offset(offset).limit(limit).all()

@app.get("/api/v1/entries/{entry_id}", response_model=EntryOut, dependencies=[Depends(authenticate)])
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    row = db.query(Entry).filter(Entry.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found.")
    return row

@app.patch("/api/v1/entries/{entry_id}", response_model=EntryOut, dependencies=[Depends(authenticate)])
def update_entry(entry_id: int, payload: EntryUpdate, db: Session = Depends(get_db)):
    row = db.query(Entry).filter(Entry.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found.")
    updates = payload.model_dump(exclude_unset=True)
    if "category" in updates and updates["category"] is not None:
        updates["category"] = updates["category"].strip().lower()
        if updates["category"] not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=422, detail=f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}")
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row

@app.delete("/api/v1/entries/{entry_id}", dependencies=[Depends(authenticate)])
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    row = db.query(Entry).filter(Entry.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found.")
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": entry_id}

@app.get("/api/v1/dashboard", dependencies=[Depends(authenticate)])
def dashboard(db: Session = Depends(get_db)):
    rows = db.query(Entry).all()
    counts = {}
    for row in rows:
        counts[row.category] = counts.get(row.category, 0) + 1
    active_goals = sum(1 for row in rows if row.category == "goal" and row.status == "active")
    return {
        "total_entries": len(rows),
        "by_category": counts,
        "active_goals": active_goals,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }


@app.post("/api/v1/ai/summary", dependencies=[Depends(authenticate)])
def ai_summary(db: Session = Depends(get_db)):
    rows = db.query(Entry).order_by(Entry.created_at.desc()).limit(100).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No entries to summarize.")

    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server.")

    lines = []
    for r in rows[:50]:
        details = (r.details or "").strip().replace("\n", " ")[:120]
        lines.append(f"- {r.created_at.date()}: [{r.category}] {r.title}" + (f" — {details}" if details else ""))

    entries_text = "\n".join(lines)
    prompt = f"""You are a personal life coach AI. Analyze these life tracking entries and provide:
1. A brief summary of recent activity
2. Patterns or trends you notice
3. One encouraging insight
4. One small, actionable suggestion for next week

Entries:
{entries_text}

Keep it under 200 words. Be encouraging, concise, and personal."""

    import json, urllib.request, urllib.error

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            summary = result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise HTTPException(status_code=502, detail=f"Groq API error ({e.code}): {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(e)}")

    return {"summary": summary, "entries_count": len(rows)}


@app.post("/api/v1/ai/goals", dependencies=[Depends(authenticate)])
def ai_goals(db: Session = Depends(get_db)):
    rows = db.query(Entry).order_by(Entry.created_at.desc()).limit(100).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No entries to base goals on.")

    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server.")

    lines = []
    for r in rows[:50]:
        details = (r.details or "").strip().replace("\n", " ")[:120]
        lines.append(f"- {r.created_at.date()}: [{r.category}] {r.title}" + (f" — {details}" if details else ""))

    entries_text = "\n".join(lines)
    prompt = f"""You are a personal life coach AI. Based on these tracking entries, suggest 3 specific, achievable goals for the next week. Make them SMART (Specific, Measurable, Achievable, Relevant, Time-bound). Keep each under 25 words. Be encouraging.

Entries:
{entries_text}

Format as a simple numbered list."""

    import json, urllib.request, urllib.error

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 400,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            text = result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise HTTPException(status_code=502, detail=f"Groq API error ({e.code}): {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(e)}")

    return {"goals": text, "entries_count": len(rows)}


@app.post("/api/v1/ai/plan", dependencies=[Depends(authenticate)])
def ai_plan(db: Session = Depends(get_db)):
    rows = db.query(Entry).order_by(Entry.created_at.desc()).limit(100).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No entries to base a plan on.")

    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server.")

    lines = []
    for r in rows[:50]:
        details = (r.details or "").strip().replace("\n", " ")[:120]
        lines.append(f"- {r.created_at.date()}: [{r.category}] {r.title}" + (f" — {details}" if details else ""))

    entries_text = "\n".join(lines)
    prompt = f"""You are a personal life coach AI. Based on these tracking entries, create a simple weekly schedule (Monday–Sunday) with one suggested focus or activity per day. Keep it realistic and balanced. Include rest days. Each day under 20 words.

Entries:
{entries_text}

Format as a simple numbered list by day of week."""

    import json, urllib.request, urllib.error

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            text = result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise HTTPException(status_code=502, detail=f"Groq API error ({e.code}): {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(e)}")

    return {"plan": text, "entries_count": len(rows)}


@app.post("/api/v1/ai/ask", dependencies=[Depends(authenticate)])
def ai_ask(payload: dict, db: Session = Depends(get_db)):
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required.")

    rows = db.query(Entry).order_by(Entry.created_at.desc()).limit(100).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No entries to answer from.")

    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server.")

    lines = []
    for r in rows[:80]:
        details = (r.details or "").strip().replace("\n", " ")[:150]
        lines.append(f"- {r.created_at.date()}: [{r.category}] {r.title}" + (f" — {details}" if details else ""))

    entries_text = "\n".join(lines)
    prompt = f"""You are a personal life coach AI. Answer the user's question using ONLY the tracking entries below. If the answer isn't in the entries, say so honestly. Be concise, encouraging, and personal.

User question: {question}

Entries:
{entries_text}

Keep answer under 150 words."""

    import json, urllib.request, urllib.error

    payload_json = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 400,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload_json,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            answer = result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise HTTPException(status_code=502, detail=f"Groq API error ({e.code}): {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(e)}")

    return {"answer": answer, "entries_count": len(rows)}
