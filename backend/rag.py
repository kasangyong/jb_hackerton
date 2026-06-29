# -*- coding: utf-8 -*-
"""
평생곁에 — 자산 케어(F1) 하이브리드 RAG 엔진
  검색: BM25(sparse) + BGE-M3(dense) → RRF 융합
  생성: EXAONE-3.5-2.4B (Ollama, 로컬·무료·CPU 가능)
  안전: 근거 미달 시 LLM을 부르지 않고 '상담사 연결'로 폴백(환각 방지 가드레일)

문서는 backend/docs/*.md 를 문단 단위로 잘라 색인합니다.
임베딩은 backend/docs/.emb_cache.json 에 캐시 → 재시작이 빠릅니다.
"""
import os, re, glob, json, hashlib
import numpy as np
import requests
from rank_bm25 import BM25Okapi

# ---- 설정 (환경변수로 덮어쓸 수 있음) ----
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL  = os.environ.get("LLM_MODEL",  "exaone3.5:2.4b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")
DOCS_DIR   = os.path.join(os.path.dirname(__file__), "docs")
CACHE_PATH = os.path.join(DOCS_DIR, ".emb_cache.json")

TOP_K      = 4        # 답변에 넣을 근거 개수
RELEVANCE_THRESHOLD = 0.55   # dense 최고 유사도가 이보다 낮으면 '근거 없음' → 상담사 연결
                             # (bge-m3 실측: 관련질문 0.68~0.80 / 범위밖 0.45 → 0.55가 안전 경계)
RRF_K      = 60

SYSTEM_PROMPT = (
    "당신은 '평생곁에'의 금융비서입니다. 전북·전남에 사는 어르신에게 금융을 아주 쉽게 설명합니다.\n"
    "반드시 지킬 규칙:\n"
    "1) 아래 [근거] 안에 있는 내용만 사용해 답하세요. [근거]에 없는 내용은 절대 지어내지 마세요.\n"
    "2) [근거]로 답할 수 없으면 정확히 이렇게만 답하세요: "
    "'제가 확실히 모르는 내용이에요. 가까운 영업점 상담사에게 연결해 드릴게요.'\n"
    "3) 어르신이 이해하기 쉽게, 짧고 따뜻하게 3~4문장 이내로 답하세요. 어려운 용어는 풀어서 말하세요.\n"
    "4) 금액·나이·기간 같은 숫자는 [근거]에 적힌 그대로 정확히 말하세요.\n"
    "5) 사기·송금이 의심되면 단정해서 권하지 말고 멈추라고 안내하세요."
)


def _tokenize(text):
    """한국어 형태소 분석기 없이 동작하는 가벼운 토크나이저.
    단어 + 한글 2-gram 을 함께 넣어 BM25 매칭률을 높인다."""
    text = text.lower()
    words = re.findall(r"[가-힣a-z0-9]+", text)
    toks = []
    for w in words:
        toks.append(w)
        if re.match(r"[가-힣]", w) and len(w) >= 2:
            toks += [w[i:i+2] for i in range(len(w) - 1)]
    return toks


def _split_docs():
    """docs/*.md 를 (제목, 섹션, 문단) 청크 목록으로.
    각 청크에 '제목 · 섹션'을 함께 담아(embed) 검색 맥락을 강화한다."""
    chunks = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.md"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        # 제목 = 첫 번째 '# ' 헤딩, 없으면 파일명
        m = re.search(r"^#\s+(.+)$", raw, re.M)
        title = m.group(1).strip() if m else os.path.splitext(os.path.basename(path))[0]
        # '## 출처'(인용 URL 목록) 이후는 임베딩에서 제외 — 검색을 오염시키지 않도록
        raw = re.split(r"^#{1,6}\s*출처", raw, flags=re.M)[0]

        heading = title
        buf = []

        def flush():
            para = re.sub(r"\s*\n\s*", " ", " ".join(buf)).strip()
            buf.clear()
            if len(para) >= 15:
                # 임베딩/BM25 대상 텍스트엔 섹션 맥락을 앞에 붙인다
                embed = f"{title} · {heading} — {para}"
                chunks.append({"title": title, "heading": heading,
                               "text": para, "embed": embed})

        for line in raw.splitlines():
            h = re.match(r"^#{1,6}\s+(.+)$", line)
            if h:
                flush()
                heading = h.group(1).strip()
            elif line.strip() == "":
                flush()
            else:
                buf.append(line.strip().lstrip("-").strip())
        flush()
    return chunks


class RagEngine:
    def __init__(self):
        self.chunks = []
        self.emb = None        # (N, D) 정규화된 임베딩
        self.bm25 = None
        self.ready = False
        self.error = None

    # ---------- Ollama ----------
    def _embed(self, text):
        r = requests.post(f"{OLLAMA_URL}/api/embeddings",
                          json={"model": EMBED_MODEL, "prompt": text}, timeout=120)
        r.raise_for_status()
        v = np.array(r.json()["embedding"], dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def _chat(self, system, user):
        r = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": LLM_MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 320},
        }, timeout=180)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    # ---------- 색인 ----------
    def build(self):
        try:
            self.chunks = _split_docs()
            if not self.chunks:
                raise RuntimeError("docs 폴더에 문서가 없습니다.")
            cache = {}
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, encoding="utf-8") as f:
                    cache = json.load(f)
            vecs, new = [], 0
            for c in self.chunks:
                key = hashlib.sha1((EMBED_MODEL + "::" + c["embed"]).encode("utf-8")).hexdigest()
                if key in cache:
                    v = np.array(cache[key], dtype=np.float32)
                else:
                    v = self._embed(c["embed"]); cache[key] = v.tolist(); new += 1
                vecs.append(v)
            self.emb = np.vstack(vecs)
            self.bm25 = BM25Okapi([_tokenize(c["embed"]) for c in self.chunks])
            if new:
                with open(CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(cache, f)
            self.ready = True
            print(f"[RAG] 색인 완료 — 청크 {len(self.chunks)}개 (신규 임베딩 {new}개), 모델 {LLM_MODEL}")
        except Exception as e:
            self.error = str(e)
            self.ready = False
            print(f"[RAG] 색인 실패: {e}")
            print("      → Ollama가 켜져 있는지, 모델을 받았는지 확인하세요:")
            print("        ollama pull exaone3.5:2.4b && ollama pull bge-m3")

    @property
    def n_chunks(self):
        return len(self.chunks)

    # ---------- 검색 (RRF) ----------
    def search(self, query, k=TOP_K):
        q = self._embed(query)
        dense = self.emb @ q                       # 코사인 유사도(정규화됨)
        sparse = np.array(self.bm25.get_scores(_tokenize(query)), dtype=np.float32)

        dense_rank = {i: r for r, i in enumerate(np.argsort(-dense))}
        sparse_rank = {i: r for r, i in enumerate(np.argsort(-sparse))}
        fused = {}
        for i in range(len(self.chunks)):
            fused[i] = 1.0 / (RRF_K + dense_rank[i]) + 1.0 / (RRF_K + sparse_rank[i])
        order = sorted(fused, key=lambda i: -fused[i])[:k]
        hits = [{"title": self.chunks[i]["title"], "heading": self.chunks[i]["heading"],
                 "text": self.chunks[i]["text"], "score": float(dense[i])} for i in order]
        return hits, float(dense.max())

    # ---------- 답변 ----------
    def answer(self, query):
        query = (query or "").strip()
        if not query:
            return {"answer": "무엇이 궁금하신지 말씀해 주세요.", "sources": [], "guardrail": False}
        if not self.ready:
            return {"answer": "지금은 AI 비서를 준비 중이에요. 잠시 후 다시 시도하거나 상담사에게 연결해 드릴게요.",
                    "sources": [], "guardrail": True, "error": self.error}

        hits, top = self.search(query)
        # 가드레일 1: 근거가 약하면 LLM을 부르지 않고 안전하게 폴백
        if top < RELEVANCE_THRESHOLD:
            return {"answer": "제가 확실히 모르는 내용이에요. 가까운 영업점 상담사에게 연결해 드릴게요.",
                    "sources": [], "guardrail": True}

        context = "\n".join(f"[근거 {i+1}] ({h['title']} · {h['heading']}) {h['text']}" for i, h in enumerate(hits))
        user = f"{context}\n\n[질문]\n{query}"
        try:
            ans = self._chat(SYSTEM_PROMPT, user)
        except Exception as e:
            return {"answer": "지금 잠시 연결이 어려워요. 가까운 영업점 상담사에게 연결해 드릴게요.",
                    "sources": [], "guardrail": True, "error": str(e)}

        # 가드레일 2: 모델이 '모른다'고 답하면 출처를 붙이지 않는다
        guard = "상담사에게 연결" in ans and "모르" in ans
        sources = [] if guard else list(dict.fromkeys(h["title"] for h in hits))
        return {"answer": ans, "sources": sources, "guardrail": guard}
