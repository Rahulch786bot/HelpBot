from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db
from app.graph import run_query


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="HelpBot API", version="1.0.0", lifespan=lifespan)

# Wide-open CORS is fine for this take-home deployment (single public
# frontend, no auth/session data at stake). Would be locked down to the
# actual frontend origin in a real production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    final_answer: str
    intent: str
    handled_by: str
    trace: list[str]
    rag_citations: list[dict] = []
    rag_confidence: float | None = None
    ticket_result: dict | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    result = run_query(req.query.strip())
    return ChatResponse(
        final_answer=result.get("final_answer", "Something went wrong -- no answer was produced."),
        intent=result.get("intent", "unknown"),
        handled_by=result.get("handled_by", "unknown"),
        trace=result.get("trace", []),
        rag_citations=result.get("rag_citations", []),
        rag_confidence=result.get("rag_confidence"),
        ticket_result=result.get("ticket_result"),
    )


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket
