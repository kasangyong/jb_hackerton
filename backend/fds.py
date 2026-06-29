# -*- coding: utf-8 -*-
"""
평생곁에 — F2 거래단 사기 방어(FDS) 2층 엔진
  1층: 2024 FDS 가이드라인 룰 (고령·신규수취인·고액·심야) — 설명가능
  2층: 사용자별 평소 거래 베이스라인 대비 이탈 (z-score·신규수취인·시간대)
  → 가중 위험 스코어 → 신호등(🟢 안전 / 🟡 주의 / 🔴 위험)

demo/index.html 의 evaluate() 와 동일한 판정을 내도록 1:1 포팅했다.
같은 300만원도 '평소 패턴' 유무로 통과/차단이 갈린다.
"""
import math


def won(n):
    """123456 → '123,456' (천 단위 콤마, 한국식)"""
    return f"{int(round(n)):,}"


def _mean(a):
    return sum(a) / len(a)


def _pstd(a):
    """모표준편차. JS의 `... || 1`처럼 0이면 1로 보정(0으로 나눔 방지)."""
    m = _mean(a)
    v = sum((x - m) ** 2 for x in a) / len(a)
    return math.sqrt(v) or 1.0


def evaluate(age, is_new, known, amount, base_amounts, usual_hours, hour):
    """거래 한 건을 평가해 위험 신호등과 사유를 반환."""
    flags = []

    # ── 1층: FDS 가이드라인 룰 ──
    if age >= 65 and is_new and amount >= 1_000_000:
        flags.append({"layer": 1,
                      "text": f"고령 계좌 → 신규 수취인에게 {won(amount)}원 (100만원↑)", "pts": 50})
    if hour < 6:
        flags.append({"layer": 1, "text": "심야(0~6시) 시간대 거래", "pts": 20})

    # ── 2층: 개인화 베이스라인 이탈 ──
    if not known:
        flags.append({"layer": 2, "text": "평생 처음 보는 수취인", "pts": 25})
    if base_amounts:
        m = _mean(base_amounts)
        sd = _pstd(base_amounts)
        z = (amount - m) / sd
        if z >= 3:
            flags.append({"layer": 2,
                          "text": f"평소(약 {won(round(m))}원)보다 비정상적으로 큰 금액 (z={z:.1f})",
                          "pts": 35})
    else:
        m = amount
    if hour not in usual_hours:
        flags.append({"layer": 2, "text": "평소 거래하지 않던 시간대", "pts": 15})

    # ── 가중 합산 → 신호등 ──
    score = min(100, sum(f["pts"] for f in flags))
    if score >= 70:
        level, cls, action = "위험 🔴", "danger", "stop"
        say = ("잠깐만요. 평소와 너무 다른 거래예요. 보이스피싱이 의심됩니다. "
               "지금 멈추고 가족이나 112에 확인하세요.")
    elif score >= 35:
        level, cls, action = "주의 🟡", "warn", "warn"
        say = "이 거래가 평소와 조금 달라요. 정말 보내는 게 맞는지 한 번만 더 확인할게요."
    else:
        level, cls, action = "안전 🟢", "safe", "go"
        say = ("평소처럼 아는 분께 보내는 거래로 보입니다." if known
               else "평소 거래 패턴과 비슷합니다.") + " 안전하게 송금할게요."

    return {"flags": flags, "score": score, "level": level,
            "cls": cls, "action": action, "say": say, "mean": m}
