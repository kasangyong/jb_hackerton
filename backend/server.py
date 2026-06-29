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
import os, json
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import rag
import fds
import reputation

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
    account: str = ""        # 수취계좌(평판 조회용)


@app.get("/health")
def health():
    return {"ok": ENGINE.ready, "llm": rag.LLM_MODEL, "embed": rag.EMBED_MODEL,
            "docs": ENGINE.n_chunks, "blacklist": reputation.count(), "error": ENGINE.error}


@app.get("/stats")
def stats():
    """공공데이터 기반 사기 통계(번들 표본 또는 fetch_stats.py 갱신본)."""
    try:
        with open(os.path.join(os.path.dirname(__file__), "fraud_stats.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@app.post("/chat")
def chat(inp: ChatIn):
    return ENGINE.answer(inp.message)


@app.post("/fds")
def fds_eval(inp: FdsIn):
    """F2 거래 사기 방어 — 2층 룰/베이스라인 + 수취계좌 평판 조회. (LLM 불필요, 즉시 응답)"""
    res = fds.evaluate(inp.age, inp.isNew, inp.known, inp.amount,
                       inp.baseAmounts, inp.usualHours, inp.hour)
    # 수취계좌 평판: 사기 신고 이력 계좌면 점수 무시하고 '완전 차단'
    if inp.account and reputation.is_fraud(inp.account):
        res["flags"].insert(0, {"layer": "평판",
                                "text": "사기 신고 이력이 있는 계좌 (수취계좌 평판 조회)", "pts": 100})
        res.update(score=100, level="위험 🔴", cls="danger", action="stop", blacklisted=True,
                   say="이 계좌는 사기 신고 이력이 있어요. 절대 보내면 안 됩니다. 송금을 멈췄습니다.")
    return res


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
