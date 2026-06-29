# -*- coding: utf-8 -*-
"""
평생곁에 — 로컬 백엔드 서버 (FastAPI)
  POST /chat   {"message": "..."}  → {"answer", "sources", "guardrail"}
  GET  /health                     → 상태/모델/문서 수

실행:
  pip install -r requirements.txt
  ollama pull exaone3.5:2.4b && ollama pull bge-m3   # 한 번만
  python server.py
  → http://127.0.0.1:8000  (데모 index.html이 이 주소로 연결됨)
"""
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import rag
import fds

ENGINE = rag.RagEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[server] 색인을 만드는 중… (첫 실행은 임베딩 때문에 수십 초 걸릴 수 있어요)")
    ENGINE.build()
    yield


app = FastAPI(title="평생곁에 RAG", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 데모를 file:// 또는 어디서 열어도 호출 가능하게
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str


class FdsIn(BaseModel):
    amount: int
    age: int = 70
    isNew: bool = False
    known: bool = True
    baseAmounts: List[int] = []
    usualHours: List[int] = []
    hour: int = 14


@app.get("/health")
def health():
    return {"ok": ENGINE.ready, "llm": rag.LLM_MODEL, "embed": rag.EMBED_MODEL,
            "docs": ENGINE.n_chunks, "error": ENGINE.error}


@app.post("/chat")
def chat(inp: ChatIn):
    return ENGINE.answer(inp.message)


@app.post("/fds")
def fds_eval(inp: FdsIn):
    """F2 거래 사기 방어 — 거래 한 건 평가 → 위험 신호등+사유. (LLM 불필요, 즉시 응답)"""
    return fds.evaluate(inp.age, inp.isNew, inp.known, inp.amount,
                        inp.baseAmounts, inp.usualHours, inp.hour)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
