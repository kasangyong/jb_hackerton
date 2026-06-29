# JB금융그룹 Fin:AI Challenge — 구현 계획 (plan.md)

> **서비스(가칭)**: 「평생곁에」 — 지방 고령 고객 생애주기 라이프케어 + 거래단 사기방어 AI 에이전트
> **주제**: 지정주제 1 (개인 라이프케어 AI)
> **근거 문서**: [research.md](research.md) (시장·기술·경쟁 리서치)
> **재사용 코드베이스**: `c:/Users/82102/Desktop/develop/kftc-rag/kftc-rag` (공정위 의결서 하이브리드 RAG — 검증된 본인 코드)
> **작성일**: 2026-06-09 · **예선 마감**: 2026-06-12 10:00

---

## 0. 포지셔닝 — 이 프로젝트의 스파인 (1줄로 모든 걸 정렬)

> ## **"고령자에게 자산관리(WM)란 '불리는 것'이 아니라 '지키는 것'이다."**

- 모든 팀이 WM을 **자산 증식**(로보어드바이저, 2030 타깃)으로 풀 때, 우리는 WM을 **자산 방어(Wealth *Defense*)** 로 재정의한다 — 노후자금을 **사기·실수·인지저하**로부터 지키는 것.
- 이 한 줄이 **두 문제를 동시에 푼다**:
  1. **주제 적합성 시비 차단** — "사기방어가 왜 WM/라이프케어냐?" → "고령자의 WM은 본질적으로 자산 방어다. 지킬 자산을 잃으면 관리할 자산도 없다."
  2. **차별화** — 남들과 정반대 방향이라 심사위원 기억에 박힌다.
- **히어로(주인공) 기능 = 「송금 직전 30초」.** 보이스피싱에 속아 송금 버튼을 누르려는 그 30초에 은행이 **먼저** 개입해 노후자금을 지키는 단 하나의 장면. F1(자산케어)은 이 서사를 받치는 조연.
- 서비스명 「평생곁에」 = *평생 곁에서 지킨다*. 네이밍도 방어 컨셉과 정합.

---

## 0-1. 핵심 방침

1. **바닥부터 새로 짜지 않는다.** `kftc-rag`가 이미 **하이브리드 RAG(BM25+Dense+RRF) + 리랭커 + 리스크 스코어러 + 의도 라우터 + 가드레일 프롬프트 + FastAPI 서빙**을 완성형으로 갖고 있다. → **포크해서 도메인만 교체**한다. 이게 솔로가 3일 안에 "동작하는 PoC + 탄탄한 문서"를 동시에 잡는 유일한 길.
2. **예선 산출물 우선순위**: MVP 제안서(PPT) + 기능명세서(DOCX)가 1순위. 코드는 **F2(거래 사기 방어 = 히어로) + F1(자산케어 RAG)** 순으로 "구현 여부 O" PoC, 나머지는 설계(X).
3. **에이전트 정체성**: 단순 Q&A가 아니라 **선제 트리거(거래 이벤트 모니터 → 먼저 말 건다) + 도구 사용(RAG/FDS/알림)**. 이 부분이 `kftc-rag`에 없는 **신규 추가분**.
4. **F2는 'if문'이 아니라 '개인화 베이스라인'으로 깊이를 준다.** 은행 출신 심사위원이 룰 10개를 보면 "우리가 이미 하는 것"으로 평가절하한다. → 사용자별 **평소 거래 패턴(베이스라인) 대비 이탈**을 잡는 경량 이상탐지 층을 얹어 "FDS를 안다"는 인상을 만든다 (§5.5).

---

## 1. kftc-rag → JB 「평생곁에」 재사용 매핑 (가장 중요)

| kftc-rag 모듈 | 원래 역할 | JB에서의 변환 | 작업량 |
|---|---|---|---|
| `pipeline/loader.py` `Chunk` | 의결서 청크 + 메타(위반유형/조치유형) | **금융상품·제도·법령 청크** + 메타(상품군/대상연령/위험등급) | 메타 필드 교체 |
| `pipeline/cleaner.py` | 의결서 표/텍스트 정제 | 약관·제도 문서 정제 (거의 그대로) | 소폭 |
| `search/bm25_retriever.py` (kiwipiepy) | 한국어 BM25 | **그대로 재사용** | 0 |
| `search/dense_retriever.py` (Qdrant+BGE-M3) | 밀집 검색 | **그대로 재사용** | 0 |
| `search/hybrid_retriever.py` (RRF) | 하이브리드 융합 | **그대로 재사용** | 0 |
| `search/reranker.py` | Cross-Encoder 재정렬 | **그대로 재사용** | 0 |
| `rag/router.py` | 룰베이스 의도 분류(risk/search/direct) | **의도 재정의**(asset/fraud/explain/proactive) | 키워드 교체 |
| `rag/chain.py` `LocalLLM` | EXAONE 로컬 추론 | **그대로** (모델만 EXAONE/HyperCLOVA SEED 택1) | 모델 경로 |
| `rag/prompts.py` | 변호사 페르소나 + 할루시네이션 방지 | **고령 친화 '쉬운말 금융비서' 페르소나** | 프롬프트 재작성 |
| `risk/scorer.py` | 위반유형 가중 리스크 0~100 | **거래 사기 위험 스코어러**(룰+가중) → 신호등 | 가중치/입력 교체 |
| `api/main.py` (FastAPI lifespan 싱글턴) | /predict, /api/* | **그대로** + 신규 `/api/agent`(선제) | 엔드포인트 추가 |
| `eval/` + `eval_testset_*.json` | 검색·정답 평가 | **고령 QA 평가셋**으로 교체 | 데이터 교체 |
| `requirements.txt` | 의존성 | **그대로** + `streamlit` 추가 | +1줄 |

> 즉 **검색·서빙 인프라(전체의 60%)는 0 작업**. 우리가 새로 쓰는 건 ① 데이터(금융 문서) ② 프롬프트(쉬운말) ③ FDS 룰 ④ 에이전트 선제 트리거 ⑤ Streamlit 데모.

---

## 2. 시스템 아키텍처

```
┌──────────────────────────── 입력 ────────────────────────────┐
│  (A) 대화: 음성/텍스트  "이번 달 왜 돈이 부족해?"              │
│  (B) 거래 이벤트 스트림: {계좌, 금액, 수취인, 시각, 유형}      │  ← 은행 고유
└───────────────┬──────────────────────────────┬───────────────┘
                ▼                                ▼
        [의도 라우터 router.py]          [거래 모니터 monitor.py] (신규)
        asset/fraud/explain               이상 룰 매칭 → 트리거
                │                                │
                ▼                                ▼
   ┌──────────────────── 에이전트 오케스트레이터 (orchestrator.py, 신규) ───────────────┐
   │  plan → tool 호출 → self-check(critic) → 응답   /   선제 모드: 먼저 말 건다       │
   └───┬───────────────┬────────────────────┬──────────────────────┬──────────────────┘
       ▼               ▼                    ▼                      ▼
 [RAG 검색]       [FDS 사기탐지]        [쉬운말 생성]           [액션/연계]
 hybrid_retriever  rules.py +          chain.py(LocalLLM)      알림/상담사 핸드오프
 + chain.py        risk/scorer.py      + 쉬운말 프롬프트        (PoC: 콘솔/카드)
 (근거 인용)        → 신호등 🟢🟡🔴
       │
       ▼
 [가드레일] 근거 없음→"모름+상담사 연결" / 사기의심→"송금 멈춤" 우선
       │
       ▼
 [출력] Streamlit: 음성+큰글씨 카드 UI · 신호등 · 원터치 액션
```

---

## 3. 프로젝트 구조

```
JB금융그룹/
├─ research.md                  # 완료
├─ plan.md                      # 본 문서
├─ proposal/                    # 예선 제출물
│   ├─ MVP제안서.pptx           # (양식 채움)
│   └─ 기능명세서.docx          # (양식 채움)
└─ app/                         # PoC (kftc-rag 포크)
    ├─ requirements.txt         # kftc-rag + streamlit
    ├─ config.yaml
    ├─ data/
    │   ├─ docs/                # 금융상품·제도·법령 원문(공개)
    │   ├─ *_hybrid.json        # 청크(인덱싱용)
    │   └─ *_metadata.json
    ├─ src/
    │   ├─ pipeline/  loader.py cleaner.py indexer.py     # 재사용+메타 교체
    │   ├─ search/    bm25_retriever.py dense_retriever.py hybrid_retriever.py reranker.py  # 재사용
    │   ├─ rag/       chain.py router.py prompts.py        # 적응
    │   ├─ fraud/     monitor.py rules.py baseline.py scorer.py  # 신규(scorer는 risk/ 차용)
    │   ├─ agent/     orchestrator.py tools.py guardrail.py # 신규
    │   └─ api/       main.py                               # 재사용+엔드포인트
    ├─ ui/  app.py   # Streamlit 데모 (신규)
    └─ eval/ testset_senior.json  run_eval.py  # 평가셋 교체
```

---

## 4. 데이터 모델 (loader.py `Chunk` 적응)

kftc-rag의 `Chunk`(의결서 메타)를 금융 문서용으로 교체:

```python
# src/pipeline/loader.py  (kftc-rag Chunk 패턴 그대로, 메타 필드만 도메인 교체)
from dataclasses import dataclass
from typing import Optional

@dataclass
class Chunk:
    chunk_id: str
    page_content: str
    section: str            # "상품설명" | "유의사항" | "법령조항" | "FAQ"
    chunk_type: str         # "text" | "table"
    chunk_index: int
    total_chunks: int
    header: str
    header2: Optional[str]
    doc_id: str
    doc_title: str          # 예: "주택연금 안내", "금융소비자보호법 제17조"
    # ── 도메인 메타 (의결서 위반유형/조치유형 → 금융 메타로 치환) ──
    상품군: list[str]        # ["연금", "예적금", "보증", "대출"]
    대상연령: list[str]      # ["고령", "전연령"]
    위험등급: str            # "안전" | "주의" | "고위험"  (불완전판매·복잡상품 표시)
    근거유형: list[str]      # ["상품약관", "법령", "가이드라인"]
    출처: str               # 인용 표기용 (법령명+조문, 상품명)
```

거래 사기탐지용 신규 모델:

```python
# src/fraud/monitor.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TxEvent:
    account_id: str
    amount: int
    counterparty: str        # 수취인
    counterparty_is_new: bool # 과거 거래 없는 계좌 여부
    channel: str             # "모바일" | "ATM" | "창구"
    ts: datetime
    holder_age: int          # 계좌주 연령
    tx_type: str             # "이체" | "출금"
```

---

## 5. 컴포넌트별 구현 + 코드 스니펫

### 5.1 검색 인프라 — **재사용 (작업 0)**
`hybrid_retriever.py`의 RRF 융합을 그대로 사용. 호출부만 새 데이터로:

```python
# kftc-rag/src/search/hybrid_retriever.py 의 reciprocal_rank_fusion — 그대로 사용
def reciprocal_rank_fusion(*result_lists, k: int = 60):
    scores: dict[str, float] = {}
    for results in result_lists:
        for rank, (doc_id, _) in enumerate(results):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

# 사용
retriever = KFTCHybridRetriever(chunks, reranker_model=cfg.get("reranker"))
hits = retriever.search("주택연금 받으면서 기초연금도 받을 수 있어?", top_k=5)
```

### 5.2 의도 라우터 — router.py 키워드 교체

```python
# src/rag/router.py  (kftc-rag classify_intent 패턴 재사용, 의도만 재정의)
_FRAUD_KEYWORDS  = ["검찰", "경찰", "금감원", "수사", "안전계좌", "납치", "벌금",
                    "택배", "환급", "보안카드", "원격", "앱 깔", "url", "링크"]
_ASSET_KEYWORDS  = ["연금", "예금", "적금", "만기", "이자", "상속", "증여", "보험금", "의료비"]
_EXPLAIN_KEYWORDS= ["왜", "뭐야", "무슨 뜻", "어떻게", "쉽게", "설명"]

def classify_intent(text: str) -> str:
    for kw in _FRAUD_KEYWORDS:                 # 사기 의심이 최우선
        if kw in text: return "fraud"
    for kw in _ASSET_KEYWORDS:
        if kw in text: return "asset"
    for kw in _EXPLAIN_KEYWORDS:
        if kw in text: return "explain"
    return "asset"   # 기본값
```

### 5.3 RAG 체인 + 쉬운말 프롬프트 — prompts.py 재작성

`chain.py`의 `LocalLLM`(EXAONE 로컬 추론)·`KFTCRagChain`은 그대로. 프롬프트만 고령 친화로:

```python
# src/rag/prompts.py  (kftc-rag LAWYER_SYSTEM_PROMPT 의 '근거 인용 + 할루시네이션 방지' 골격 유지)
SENIOR_SYSTEM_PROMPT = """\
당신은 지방 어르신을 돕는 친절한 금융 도우미입니다.

[말투 규칙]
1. 짧고 쉬운 문장. 한 번에 하나만 설명.
2. 어려운 금융용어는 쓰지 말고, 꼭 필요하면 바로 쉬운 말로 풀어 쓰기.
   (예: "유동성" → "필요할 때 바로 찾을 수 있는 돈")
3. 숫자는 또박또박. "약 120만원" 처럼.

[정확성 규칙 — 반드시 지킬 것]
4. 반드시 제공된 [근거 자료]에 있는 내용만 말하세요.
5. 자료에 없으면 추측하지 말고 "정확한 건 가까운 영업점이나 상담원에게 확인해 드릴게요"라고 답하세요.
6. 답변 끝에 근거를 한 줄로 표시: (근거: 주택연금 안내 / 금융소비자보호법 제17조)

[안전 규칙]
7. '검찰/경찰/금감원'을 사칭하거나 '안전계좌 이체'를 요구하는 정황이면, 답변보다 먼저 경고하세요.
"""

SENIOR_ANSWER_PROMPT = """\
[어르신 질문]
{question}

[근거 자료]
{context}

위 [근거 자료]만 사용해서, 어르신이 이해하기 쉽게 3문장 이내로 답하세요.
마지막 줄에 근거 출처를 표시하세요.
"""
```

### 5.4 사기탐지 — **2층 구조: 가이드라인 룰 + 개인화 베이스라인 이상탐지** (히어로 기능 F2)

> 핵심 설계 의도: 룰만 쓰면 "if문"으로 평가절하된다. **"이 어르신의 평소와 다른가"** 를 잡는 개인화 층을 얹어, 같은 100만원 이체라도 *평소 100만원씩 자식에게 보내던 분*과 *평생 처음 큰돈을 낯선 계좌로 보내는 분*을 구분한다. 이게 진짜 FDS의 사고방식.

**(1층) 설명가능 룰 — 2024 FDS 가이드라인 기반**
```python
# src/fraud/rules.py
from .monitor import TxEvent

def evaluate(tx: TxEvent) -> list[tuple[str, int]]:
    """가이드라인 시나리오 매칭 → (사유, 가중치) 리스트."""
    flags: list[tuple[str, int]] = []
    if tx.holder_age >= 65 and tx.counterparty_is_new and tx.amount >= 1_000_000:
        flags.append(("고령 계좌 → 신규 수취인 100만원 이상 이체", 50))
    if tx.holder_age >= 65 and tx.channel == "ATM" and tx.tx_type == "출금" and tx.amount >= 3_000_000:
        flags.append(("고령자 ATM 고액 출금(대면편취 의심)", 45))
    if tx.ts.hour in range(0, 6):
        flags.append(("심야 시간대 거래", 20))
    return flags
```

**(2층) 개인화 베이스라인 — 사용자별 '평소'를 학습해 이탈 탐지**
```python
# src/fraud/baseline.py
from dataclasses import dataclass, field
from statistics import mean, pstdev
from .monitor import TxEvent

@dataclass
class UserBaseline:
    """계좌별 평소 거래 프로필 (과거 거래로 1회 구축, 온라인 갱신 가능)."""
    amounts: list[int] = field(default_factory=list)
    usual_hours: set[int] = field(default_factory=set)
    known_counterparties: set[str] = field(default_factory=set)

    def update(self, tx: TxEvent) -> None:
        self.amounts.append(tx.amount)
        self.usual_hours.add(tx.ts.hour)
        self.known_counterparties.add(tx.counterparty)

    def novelty(self, tx: TxEvent) -> list[tuple[str, int]]:
        """평소 대비 이탈을 (사유, 가중치)로 점수화 — 전부 설명가능."""
        flags: list[tuple[str, int]] = []
        if tx.counterparty not in self.known_counterparties:
            flags.append(("평생 처음 보는 수취인", 25))
        if len(self.amounts) >= 5:
            mu, sd = mean(self.amounts), pstdev(self.amounts) or 1
            z = (tx.amount - mu) / sd
            if z >= 3:   # 평소 금액 분포에서 3σ 이상 벗어남
                flags.append((f"평소({mu:,.0f}원)보다 비정상적으로 큰 금액 (z={z:.1f})", 35))
        if tx.ts.hour not in self.usual_hours:
            flags.append(("평소 거래하지 않던 시간대", 15))
        return flags
```
> 합성 데이터라도 "이 사용자의 과거 거래 5건+"으로 베이스라인을 만들면 데모에서 *"같은 금액인데 한 명은 통과, 한 명은 차단"*을 보여줄 수 있다 → 심사위원에게 "개인화 FDS"로 각인. 본선 확장: 베이스라인 → Isolation Forest/GNN.

### 5.5 사기 위험 신호등 — risk/scorer.py 패턴 차용 (룰 + 베이스라인 통합)

kftc-rag `RiskScorer.score_from_chunks`(위반유형 가중합 → 0~100 → 레벨)의 구조를 그대로 차용:

```python
# src/fraud/scorer.py  (kftc-rag risk/scorer.py 의 가중합+레벨 패턴 재사용)
from dataclasses import dataclass

@dataclass
class FraudResult:
    score: int                  # 0~100
    level: str                  # "안전🟢" | "주의🟡" | "위험🔴"
    reasons: list[str]
    action: str                 # 권고 조치

def score(flags: list[tuple[str, int]]) -> FraudResult:
    s = min(100, sum(w for _, w in flags))     # 가중치 합산(상한 100)
    if   s >= 70: level, action = "위험🔴", "지금 송금을 멈추고, 가족이나 112/영업점에 확인하세요."
    elif s >= 35: level, action = "주의🟡", "이 거래가 맞는지 한 번 더 확인할게요."
    else:         level, action = "안전🟢", "정상적인 거래로 보입니다."
    return FraudResult(s, level, [r for r, _ in flags], action)
```

### 5.6 에이전트 오케스트레이터 — **신규** (선제성 = 'Agent' 정체성)

LangGraph 풀스택은 3일엔 과함 → **경량 상태머신**으로 동일 개념(plan→tool→critic) 구현:

```python
# src/agent/orchestrator.py
from ..rag.router import classify_intent
from ..rag.chain import KFTCRagChain
from ..fraud import rules, scorer
from .guardrail import enforce

class SeniorAgent:
    def __init__(self, rag: KFTCRagChain):
        self.rag = rag

    # (1) 반응형: 어르신이 물었을 때
    def respond(self, text: str) -> dict:
        intent = classify_intent(text)
        if intent == "fraud":
            return {"type": "warn",
                    "message": "⚠️ 보이스피싱이 의심됩니다. 절대 송금하지 마세요.",
                    "action": "영업점/112 확인"}
        result = self.rag.answer(text)                 # 근거 인용 RAG
        return enforce({"type": "answer",
                        "message": result.answer,
                        "sources": result.sources})    # 가드레일 통과

    # (2) 선제형: 거래 이벤트가 들어왔을 때 — '먼저' 말 건다 (히어로 기능)
    def on_transaction(self, tx, baseline) -> dict | None:
        # 1층 가이드라인 룰 + 2층 개인화 베이스라인 이탈을 합산
        flags = rules.evaluate(tx) + baseline.novelty(tx)
        fr = scorer.score(flags)
        baseline.update(tx)                 # 정상 거래는 평소 패턴에 흡수
        if fr.level.startswith("안전"):
            return None
        return {"type": "proactive_alert",
                "level": fr.level, "reasons": fr.reasons, "action": fr.action}
```

```python
# src/agent/guardrail.py  (kftc-rag 프롬프트의 '근거 없으면 모름' 원칙을 코드로 강제)
NO_EVIDENCE = "정확한 건 가까운 영업점이나 상담원에게 확인해 드릴게요."
def enforce(resp: dict) -> dict:
    if resp.get("type") == "answer" and not resp.get("sources"):
        resp["message"] = NO_EVIDENCE          # 근거 0 → 단정 금지
        resp["action"]  = "상담사 연결"
    return resp
```

### 5.7 데모 UI — Streamlit **신규** (gongmo_idea 경험 활용)

```python
# ui/app.py
import streamlit as st
from src.agent.orchestrator import SeniorAgent
# ... rag/agent 초기화(싱글턴) ...

st.set_page_config(page_title="평생곁에", layout="centered")
st.markdown("<h1 style='font-size:2.2rem'>💚 평생곁에</h1>", unsafe_allow_html=True)

# 선제 알림 데모: 의심 거래 버튼
if st.button("📥 [데모] 의심 거래 들어옴 (70대·신규수취인·300만원)"):
    alert = agent.on_transaction(demo_tx)
    if alert:
        st.error(f"{alert['level']}  {' / '.join(alert['reasons'])}\n\n👉 {alert['action']}")

q = st.text_input("어르신, 무엇을 도와드릴까요?")
if q:
    r = agent.respond(q)
    box = st.error if r["type"] == "warn" else st.success
    box(r["message"])                 # 큰 글씨·고대비 카드
    if r.get("sources"):
        st.caption("근거: " + ", ".join(s.출처 for s in r["sources"]))
```

### 5.8 서빙 — api/main.py 재사용 + `/api/agent` 추가
kftc-rag의 `lifespan` 싱글턴 패턴(전역 `_retriever`,`_rag_chain` 1회 로드) 그대로. Streamlit이 이 API를 호출하거나, PoC는 in-process 직접 호출로 단순화.

---

## 6. 데이터 확보 계획 (전부 공개)

| 용도 | 출처 | 처리 |
|---|---|---|
| RAG 지식(F1) | 주택연금·기초연금 안내, 예적금/보증 상품설명서, 금융소비자보호법, 고령금융소비자 보호기준 | PDF→텍스트→`*_hybrid.json`/`*_metadata.json` (kftc-rag `make_dataset_from_docs.py` 재사용) |
| FDS 룰(F2) | 2024 FDS 가이드라인 시나리오, 경찰청·금감원 보이스피싱 유형 | `rules.py`에 룰로 인코딩 |
| 사기 텍스트(확장) | KorCCVi 데이터셋(GitHub) | 본선 단계 분류 모델용 |
| 거래 데모 | **합성 데이터**(개인정보 0) | `monitor.py` 시드 |
| 평가셋 | 고령자 가상 질문 30~50개 자작 | kftc-rag `eval_testset_*.json` 포맷 |

---

## 7. 일정 (예선 D-3)

**D1 (오늘, 6/9)**
- [ ] `kftc-rag` → `app/` 포크, requirements 설치, Qdrant 기동 확인
- [ ] 금융 문서 5~6종 수집 → 청킹/인덱싱(`make_dataset_from_docs.py`, `run_index.py` 재사용)
- [ ] `loader.py` 메타 필드 교체 → 검색 동작 확인

**D2 (6/10) — 히어로 F2 먼저**
- [ ] `fraud/rules.py`+`baseline.py`+`scorer.py`+`monitor.py` → F2(룰+개인화 베이스라인 → 신호등) 동작
- [ ] **데모 킬러컷**: 같은 100만원 이체를 *평소 패턴 있는 A*(통과🟢) vs *낯선 수취인 B*(차단🔴)로 대비
- [ ] `prompts.py` 쉬운말 페르소나 / `router.py` 의도 교체 → F1(자산케어 RAG) 조연 동작
- [ ] `agent/orchestrator.py`+`guardrail.py` → 반응형/선제형 통합
- [ ] `ui/app.py` Streamlit 데모 — 「송금 직전 30초」 한 장면 연출 중심

**D3 (6/11~6/12 오전)**
- [ ] 데모 스크린샷 3컷 → **MVP 제안서 PPT 7장** 작성(research.md 탄약)
- [ ] **기능명세서 DOCX**(F1·F2 구현여부 O, F3·F4 설계 X) + 부록 출처
- [ ] 최종 검수 → **6/12 10:00 전 제출** (버퍼 확보)

> 본선 진출 시 로드맵(문서에 명시): GNN 이상탐지, sLLM 도메인 파인튜닝(kftc-rag `train/` 재사용), 음성 STT/TTS, 가족 연계.

---

## 8. 기술 선택 & 제약 대응

| 항목 | 선택 | 근거 |
|---|---|---|
| LLM | EXAONE-3.5-2.4B(로컬, 이미 보유) 또는 HyperCLOVA X SEED | 오프라인·한국어·JB 제휴사 정합(research §5.6) |
| 임베딩 | BGE-M3 (kftc-rag 그대로) | 한국어 강함, 코드 재사용 |
| 검색 | BM25(kiwipiepy)+Dense(Qdrant)+RRF+Reranker | kftc-rag 검증됨 |
| 사기탐지 | 룰(MVP) → GNN(확장) | 설명가능·현실적, research §5.3 |
| UI | Streamlit | gongmo_idea 경험, 데모 최속 |
| 할루시네이션 | 근거 인용 + guardrail.py + "모르면 사람" | 금융 신뢰성, research §5.4 |

---

## 9. 평가 (kftc-rag eval 재사용)

`eval/run_eval.py`(검색 Recall/정답 일치)를 그대로 쓰고, 평가셋만 고령 QA 30~50문항으로 교체. 제안서에 "검색 정확도 / 근거 인용율 / 사기룰 탐지율" 지표로 한 줄 제시 → 완성도 인상↑.

---

## 10. 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| Qdrant/모델 환경 세팅 지연 | kftc-rag 이미 동작 → 환경 재사용. 최악엔 FAISS/in-memory 폴백 |
| 3일 내 4기능 전부 무리 | F1·F2만 PoC(O), F3·F4 설계(X) — 명세서가 이를 허용 |
| 데이터 수집 시간 | 문서 5~6종으로 압축, 시나리오 2개에 집중 |
| "에이전트 맞나" 의심 | 선제 트리거(on_transaction) 데모로 증명 |
| 통계 수치 오류 | 제안서 확정 전 원문 재확인(research §10 검증 메모) |
```
