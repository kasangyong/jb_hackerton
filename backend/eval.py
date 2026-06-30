# -*- coding: utf-8 -*-
"""
간이 정확도/신뢰성 평가 — 백엔드가 떠 있을 때 실행: python eval.py
  · F1 RAG: 범위 내 질문 응답·인용률, 핵심 사실 일치, 범위 밖 질문 가드레일 거부율
  · F2 FDS: 사기계좌 차단 / 정상 통과 / 이탈 차단 판정 정확도
결과를 ../평가결과.md 로 저장한다.
"""
import os, requests

B = "http://127.0.0.1:8000"
OUT = os.path.join(os.path.dirname(__file__), "..", "평가결과.md")

# (질문, 기대 출처 키워드, 핵심 사실 키워드)
INSCOPE = [
    ("예금자보호 한도가 얼마예요?", "예금자보호", "1억"),
    ("주택연금 받으면 기초연금도 같이 받나요?", "연금", None),
    ("기초연금 한 달에 얼마 받아요?", "기초연금", "342"),
    ("정기예금 만기 전에 깨면 손해인가요?", "정기예금", None),
    ("병원비 많이 나왔는데 돌려받을 수 있나요?", "의료비", None),
    ("보이스피싱 전화 오면 어떻게 해요?", "보이스피싱", None),
    ("주택연금 몇 살부터 가입해요?", "주택연금", "55"),
    ("ELS 가입해도 예금자보호 되나요?", "예금자보호", None),
]
OUTSCOPE = ["비트코인 지금 사도 될까요?", "오늘 서울 날씨 어때요?", "좋은 주식 하나 추천해줘", "대통령이 누구야?"]
FDS = [
    ("사기계좌로 300만원(평판 차단)", dict(amount=3000000, age=73, isNew=True, known=False,
        baseAmounts=[200000, 250000, 180000], usualHours=[9, 10], hour=14, account="901-2345-0021"), "danger"),
    ("평소 큰금액도 보내던 분 300만원", dict(amount=3000000, age=71, isNew=False, known=True,
        baseAmounts=[300000, 2500000, 3000000, 320000], usualHours=[14], hour=14, account="전북 1**-4457"), "safe"),
    ("낯선 새벽 소액 50만원", dict(amount=500000, age=73, isNew=True, known=False,
        baseAmounts=[200000, 250000, 180000], usualHours=[9, 10], hour=3, account=""), "danger"),
]


def chat(q):
    return requests.post(B + "/chat", json={"message": q}, timeout=120).json()


def run():
    ans = cite = fact = factn = 0
    rows = []
    for q, src, key in INSCOPE:
        d = chat(q)
        answered = not d.get("guardrail")
        cited = bool(d.get("sources"))
        ans += answered; cite += cited
        fk = "-"
        if key:
            factn += 1
            hit = key in d["answer"].replace(",", "")
            fact += hit; fk = "✅" if hit else "❌"
        rows.append(f"| {q} | {'응답' if answered else '가드레일'} | {'O' if cited else 'X'} | {fk} |")

    guard = sum(1 for q in OUTSCOPE if chat(q).get("guardrail"))
    fok, frows = 0, []
    for name, p, exp in FDS:
        r = requests.post(B + "/fds", json=p).json()
        ok = r["cls"] == exp
        fok += ok
        frows.append(f"| {name} | 기대 {exp} / 실제 {r['cls']} (score {r['score']}) | {'✅' if ok else '❌'} |")

    n = len(INSCOPE)
    md = f"""# 평생곁에 — 간이 정확도·신뢰성 평가 결과

> `backend/eval.py` 자동 실행 결과. 로컬 EXAONE-3.5-2.4B + RAG 기준.

## 요약
| 지표 | 결과 |
|---|---|
| 범위 내 질문 **응답률** | {ans}/{n} ({ans*100//n}%) |
| 근거 **인용률** | {cite}/{n} ({cite*100//n}%) |
| 핵심 사실 **일치율** | {fact}/{factn} ({fact*100//factn if factn else 0}%) |
| 범위 밖 질문 **가드레일 거부율** | {guard}/{len(OUTSCOPE)} ({guard*100//len(OUTSCOPE)}%) |
| F2 사기탐지 **판정 정확도** | {fok}/{len(FDS)} ({fok*100//len(FDS)}%) |

## F1 RAG — 범위 내 질문
| 질문 | 응답 | 인용 | 사실 |
|---|---|---|---|
{chr(10).join(rows)}

## F1 RAG — 범위 밖(거부 기대): {guard}/{len(OUTSCOPE)} 가드레일 작동

## F2 FDS — 판정
| 케이스 | 판정 | 정확 |
|---|---|---|
{chr(10).join(frows)}

> 한계: 표본 {n}+{len(OUTSCOPE)}문항의 간이 평가다. 실서비스는 대규모 라벨셋으로 환각률·오탐율(FAR)을 정식 측정해야 한다.
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print("saved 평가결과.md")
    print(f"응답 {ans}/{n} 인용 {cite}/{n} 사실 {fact}/{factn} 거부 {guard}/{len(OUTSCOPE)} FDS {fok}/{len(FDS)}")


if __name__ == "__main__":
    run()
