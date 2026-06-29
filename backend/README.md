# 평생곁에 — 백엔드 (F1 자산 케어 RAG · F2 사기 방어 FDS)

전북·전남 어르신을 지키는 **실제 작동 백엔드**입니다.

- **F1 자산 케어 RAG** (`/chat`): 검색(BM25 + BGE-M3 + RRF)으로 근거를 찾고 **EXAONE-3.5-2.4B**(로컬·무료)로 답하며, 근거가 없으면 지어내지 않고 **상담사 연결**로 폴백(환각 방지 가드레일).
- **F2 거래단 사기 방어 FDS** (`/fds`): 1층 가이드라인 룰 + 2층 개인화 베이스라인(z-score) + **3층 수취계좌 평판 조회** → 위험 신호등. LLM이 필요 없어 **즉시 응답**. 같은 300만원도 평소 패턴 유무로 통과/차단이 갈리고, **사기 신고 이력 계좌면 점수와 무관하게 완전 차단**.
- **공공데이터 사기 통계** (`/stats`): 우체국 사기계좌·경찰청·금감원 기반 통계(번들 표본, `fetch_stats.py`로 실데이터 갱신).

```
[데모 챗 UI]   --POST /chat--> [FastAPI :8000] --검색--> docs/*.md
                                             \--생성--> Ollama(EXAONE 3.5)
[데모 사기방어] --POST /fds---> [FastAPI :8000]  2층 FDS 엔진 → 신호등🟢🟡🔴
```

## 1. 준비 (한 번만)

1) **Ollama 설치**: https://ollama.com/download (윈도우 설치파일)
2) **모델 받기** (합쳐 ~3GB):
```bash
ollama pull exaone3.5:2.4b
ollama pull bge-m3
```
3) **파이썬 패키지 설치** (이 폴더에서):
```bash
pip install -r requirements.txt
```

## 2. 실행

```bash
python server.py
```
- 처음 켜면 문서 임베딩을 만드느라 수십 초 걸립니다(다음부터는 캐시로 빠름).
- `http://127.0.0.1:8000/health` 를 브라우저로 열어 `"ok": true` 면 준비 끝.

## 3. 데모와 연결

`demo/index.html`을 브라우저로 열고 **② 자산 케어** 탭에서 질문하면,
서버가 켜져 있으면 **진짜 EXAONE**이 답하고, 꺼져 있으면 기존 예시 답변으로 자동 폴백합니다.

## 4. 빠른 점검 (서버 없이 터미널에서)

```bash
# F1 자산 케어 RAG
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"주택연금 받으면 기초연금도 같이 받을 수 있나요?\"}"

# F2 사기 방어 — 같은 300만원, 다른 결과
#  박OO(평소 큰 금액도 보냄) → 안전 🟢
curl -X POST http://127.0.0.1:8000/fds -H "Content-Type: application/json" -d "{\"amount\":3000000,\"age\":71,\"isNew\":false,\"known\":true,\"baseAmounts\":[300000,350000,280000,2500000,3000000,320000],\"usualHours\":[10,11,14,15],\"hour\":14}"
#  김OO(낯선 안전계좌) → 위험 🔴 (score 100)
curl -X POST http://127.0.0.1:8000/fds -H "Content-Type: application/json" -d "{\"amount\":3000000,\"age\":73,\"isNew\":true,\"known\":false,\"baseAmounts\":[200000,250000,180000,300000,220000],\"usualHours\":[9,10,13,16],\"hour\":14}"
```

## 4-1. 수취계좌 평판 (사기계좌 완전 차단)
- `fraud_accounts.json` 의 샘플 블랙리스트로 동작. `/fds` 요청에 `account`(수취계좌)를 넣으면, 블랙리스트에 있을 때 **점수 무시하고 즉시 🔴 차단**.
- 본 구현: 샘플 자리에 **JB 은행권 '사기이용계좌 공유 DB'** 또는 **더치트(TheCheat) API**를 연결. (무료 공개데이터에는 계좌번호가 없음 — 개인정보)

## 4-2. 공공데이터 사기 통계 갱신 (선택)
> ⚠️ 인증키는 **환경변수로만** 전달하고, 절대 코드/깃에 넣지 말 것.
```bash
# 공공데이터포털에서 데이터셋 15021794 '활용신청' → 키 발급, '오픈API' 탭에서 요청 URL 복사
$env:DATA_GO_KR_KEY="발급키"          # PowerShell
$env:DATA_GO_KR_ENDPOINT="https://api.odcloud.kr/api/15021794/v1/uddi:..."
python fetch_stats.py                  # → fraud_stats.json 실데이터로 갱신
```
키가 없어도 데모는 번들 `fraud_stats.json`(표본)으로 동작한다.

## 5. CPU 안내
- EXAONE 3.5 **2.4B**는 CPU에서도 동작합니다(답변당 몇 초~십몇 초). 시연에 충분합니다.
- 느리면: `rag.py`의 `num_predict`(답변 길이)를 줄이거나, `TOP_K`를 2로 낮추세요.

## 6. 문서 추가/수정
- `docs/` 에 `.md` 파일을 넣으면 자동 색인됩니다(서버 재시작).
- 문서를 바꾸면 `docs/.emb_cache.json` 을 지우고 다시 실행하면 새로 임베딩합니다.

## 설정(환경변수)
| 변수 | 기본값 | 설명 |
|---|---|---|
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama 주소 |
| `LLM_MODEL` | `exaone3.5:2.4b` | 생성 모델 |
| `EMBED_MODEL` | `bge-m3` | 임베딩 모델 |
