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


class BriefIn(BaseModel):
    blocks: List[dict] = []  # 차단 로그 [{who, amt, city, reason}]
    totalSaved: int = 0


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


@app.post("/brief")
def brief(inp: BriefIn):
    """은행 측 LLM 활용 — 본부 담당자용 '관제 브리핑'을 EXAONE이 차단 로그로 작성."""
    if not inp.blocks:
        return {"brief": "오늘 차단된 의심 거래가 없습니다. 전북·전남 보호 고객 거래는 정상 범위입니다."}
    lines = "\n".join(
        f"- {b.get('who','')} / ₩{int(b.get('amt',0)):,} / {b.get('city','')} / 사유: {b.get('reason','')}"
        for b in inp.blocks[:12])
    system = ("당신은 JB금융그룹 본부 사기방어 관제 담당자를 돕는 AI입니다. 아래 '차단 로그'만 근거로 "
              "관제 브리핑을 작성하세요. 규칙: 1) 로그에 있는 숫자·지역·사유만 사용하고 지어내지 말 것 "
              "2) 3~4문장의 간결한 보고체 3) 핵심 패턴과 집중 지역을 짚을 것 4) 마지막에 권고 조치 1개.")
    user = (f"[차단 로그] 아래는 평생곁에가 송금 직전에 차단한 의심 '이체(송금)' 거래 목록이다. "
            f"총 {len(inp.blocks)}건, 방어액 ₩{int(inp.totalSaved):,}\n{lines}")
    if not ENGINE.ready:
        return {"brief": "(AI 준비 중) 상황판 수치를 확인하세요.", "error": ENGINE.error}
    try:
        return {"brief": ENGINE._chat(system, user)}
    except Exception as e:
        return {"brief": "(AI 연결 오류) 상황판 수치를 확인하세요.", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
