# -*- coding: utf-8 -*-
"""
수취계좌 평판 조회 — 사기 신고 이력이 있는 계좌면 '완전 차단'.

- 데모: backend/fraud_accounts.json 의 샘플 블랙리스트로 동작.
- 본 구현: 이 자리에 JB 은행권 '사기이용계좌 공유 DB' 또는 더치트(TheCheat) API를 연결.
  ※ 무료 공공데이터(우체국 사기계좌 등)에는 '계좌번호'가 없으므로(개인정보) 실명단 대체용은 위 두 가지뿐.
"""
import os, re, json

_PATH = os.path.join(os.path.dirname(__file__), "fraud_accounts.json")


def _norm(a):
    """계좌 문자열에서 숫자만 추출(은행명·하이픈·공백 제거)."""
    return re.sub(r"\D", "", a or "")


def _load():
    s = set()
    try:
        with open(_PATH, encoding="utf-8") as f:
            for a in json.load(f).get("accounts", []):
                n = _norm(a)
                if n:
                    s.add(n)
    except Exception as e:
        print("[reputation] 블랙리스트 로드 실패:", e)
    return s


FRAUD = _load()


def is_fraud(account):
    return bool(account) and _norm(account) in FRAUD


def count():
    return len(FRAUD)
