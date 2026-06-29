# -*- coding: utf-8 -*-
"""
공공데이터포털 '우체국금융개발원 금융사기계좌 정보'(데이터셋 15021794)에서
실제 사기 통계(사기유형·연령대·평균 피해액)를 가져와 fraud_stats.json 으로 저장.

⚠️ 인증키는 코드에 넣지 말고 환경변수로만 전달한다(깃 커밋 금지).

준비:
  1) 공공데이터포털에서 해당 데이터 '활용신청' → 인증키 발급.
  2) 데이터셋 '오픈API' 탭에서 요청 URL(엔드포인트 + uddi)을 복사.
  3) 실행:
       # Windows (PowerShell)
       $env:DATA_GO_KR_KEY="발급키"
       $env:DATA_GO_KR_ENDPOINT="https://api.odcloud.kr/api/15021794/v1/uddi:xxxxxxxx"
       python fetch_stats.py

키/엔드포인트가 없으면 아무것도 덮어쓰지 않고, 데모는 번들 fraud_stats.json 으로 동작한다.
"""
import os, json, collections
import requests

KEY = os.environ.get("DATA_GO_KR_KEY")
ENDPOINT = os.environ.get("DATA_GO_KR_ENDPOINT")
OUT = os.path.join(os.path.dirname(__file__), "fraud_stats.json")


def pick(row, *names):
    for n in names:
        for k, v in row.items():
            if n in str(k):
                return v
    return None


def main():
    if not KEY or not ENDPOINT:
        print("DATA_GO_KR_KEY / DATA_GO_KR_ENDPOINT 환경변수가 필요합니다. (backend/README 참고)")
        print("→ 키 없이도 데모는 번들 fraud_stats.json(표본) 으로 동작합니다.")
        return
    rows, page = [], 1
    while True:
        r = requests.get(ENDPOINT, params={"serviceKey": KEY, "page": page, "perPage": 1000}, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        rows += data
        if len(data) < 1000:
            break
        page += 1
    if not rows:
        print("데이터가 비었습니다. 엔드포인트/키를 확인하세요.")
        return

    types, ages, loss = collections.Counter(), collections.Counter(), []
    for row in rows:
        t = pick(row, "사기유형", "유형")
        if t:
            types[str(t)] += 1
        a = pick(row, "연령")
        if a:
            ages[str(a)] += 1
        v = pick(row, "피해", "송금액", "금액")
        try:
            loss.append(float(str(v).replace(",", "")))
        except Exception:
            pass

    tot = sum(types.values()) or 1
    agetot = sum(ages.values()) or 1
    out = {
        "source": "우체국금융개발원 금융사기계좌 정보(공공데이터포털 15021794)",
        "mode": "실데이터",
        "count": len(rows),
        "byType": [{"label": k, "pct": round(v * 100 / tot, 1)} for k, v in types.most_common(4)],
        "byAge": [{"label": k, "pct": round(v * 100 / agetot, 1)} for k, v in ages.most_common(5)],
        "avgLossManwon": round(sum(loss) / len(loss) / 10000) if loss else None,
        "note": "backend/fetch_stats.py 로 갱신됨",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("저장 완료:", OUT, "| 건수", len(rows))


if __name__ == "__main__":
    main()
