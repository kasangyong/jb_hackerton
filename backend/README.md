# 평생곁에 — 백엔드 (F1 자산 케어 RAG)

전북·전남 어르신에게 금융을 쉽게 설명하는 **실제 작동 RAG**입니다.
검색(BM25 + BGE-M3 + RRF)으로 근거를 찾고, **EXAONE-3.5-2.4B**(로컬·무료)로 답하며,
근거가 없으면 지어내지 않고 **상담사 연결**로 폴백합니다(환각 방지 가드레일).

```
[데모 챗 UI] --POST /chat--> [FastAPI :8000] --검색--> docs/*.md
                                            \--생성--> Ollama(EXAONE 3.5)
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
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"주택연금 받으면 기초연금도 같이 받을 수 있나요?\"}"
```

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
