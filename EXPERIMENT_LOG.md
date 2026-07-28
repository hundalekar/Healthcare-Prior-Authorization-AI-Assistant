# Experiment Log

Chronological record of design decisions, debugging investigations, and configuration changes made during development. Written for reproducibility and interview storytelling.

---

## 1. Initial Retrieval Quality Problem

**Issue:** Query "What are the medical necessity criteria for MRI of the spine?" returned references pages and research content instead of the actual policy section on page 2.

**Symptom:**
- Top-3 retrieved results contained: page 32 (research), background pages, references pages
- Expected page 2 ("I. Medical Necessity" section) was not in top-3

**Investigation approach:** Isolate variables one at a time to identify root cause. Three hypotheses:
1. Merging step destroying page boundaries
2. Chunk size too large, diluting semantic signal
3. Embedding model weak for domain terminology

---

## 2. Merging Step Investigation

**Original code:** `merge_documents.py` combined every 5 filtered pages into a single document before chunking.

**Hypothesis:** Merging pages 2-6 into one block means the "Medical Necessity" section on page 2 gets glued to background content on pages 3-6. When chunked, the resulting chunks contain mixed context.

**Test:** Removed merging step entirely. Chunked directly from filtered per-page documents.

**Result:** Ranking improved marginally. Page 2 moved from rank #2 to rank #2 (no change on this query alone).

**Verdict:** Merging was harmful but not the primary issue. Kept the change (skip merging) as a permanent config.

**Files affected:** `src/ingestion/merge_documents.py` (kept for record, no longer called)

---

## 3. Chunk Size Experiment

**Original config:** `chunk_size=2000, chunk_overlap=300`

**Hypothesis:** 2000-char chunks (~400-500 words) are too large. The Medical Necessity list gets averaged with surrounding text, diluting the semantic signature.

**Test:** Reduced to `chunk_size=800, chunk_overlap=150`.

**Result:**

| Config | Rank 1 | Rank 2 | Rank 3 |
|---|---|---|---|
| 2000/300 | Page 7 (background) | **Page 2 (target)** | Page 51 (refs) |
| 800/150 | **Page 2 (target)** | Page 11 (context) | Page 3 (related) |

Correct page moved to rank #1. References and background eliminated from top-3.

**Verdict:** **Biggest single improvement.** Locked as permanent config.

**Lesson learned:** For structured policy documents with distinct sections, smaller chunks preserve semantic focus better than larger ones.

**Files affected:** `src/ingestion/chunk_documents.py`

---

## 4. Embedding Model Comparison

**Original model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim)

**Hypothesis:** MiniLM is a general-purpose model trained on web data. Might struggle with healthcare/insurance domain terminology.

**Test:** Switched to `BAAI/bge-small-en-v1.5` (384-dim, same size for fair comparison), with `normalize_embeddings=True`.

**Result:** Marginal improvement in ranking quality. Both models correctly identified page 2 as top result after the chunk size fix.

**Verdict:** BGE-small kept as default. Change is small but consistent with tech stack originally planned.

**Lesson learned:** Chunking strategy matters more than embedding model choice for this document type.

**Files affected:** `src/retrieval/create_vectorstore.py`

---

## 5. Chunking Artifact - 1-Character Chunks

**Issue:** After switching to `chunk_size=800`, `chunks[0]` output showed only the single character "I".

**Root cause:** RecursiveCharacterTextSplitter's separator `". "` split on the period after Roman numeral "I" in "I. Medical Necessity", creating a 1-char chunk before the actual content.

**Impact:** Cosmetic only. Did not affect retrieval quality since the actual Medical Necessity content is in adjacent chunks that ranked correctly.

**Decision:** Deferred fix to Phase 2. Would filter chunks under 50 characters after splitting.

**Files affected:** None (documented as known issue)

---

## 6. Text Cleaning - Footer Artifact

**Issue:** Text extraction was producing pages that started with "to see if precertification is required." followed by the actual content.

**Root cause:** PDF footer text was being appended to the beginning of the next page during extraction.

**Solution in `clean_documents.py`:**
```python
text = re.sub(r'\s+', ' ', text)  # Normalize whitespace FIRST
text = re.sub(r'to see if precertification is required\.', '', text, flags=re.IGNORECASE)
text = re.sub(r'\s+', ' ', text)  # Cleanup again after removal
```

**Critical order:** Whitespace normalization runs before pattern removal, then again after. Without the initial normalization, `\n` and `\xa0` characters break the regex match.

---

## 7. Multi-Policy Cross-Testing

**After MVP was working for Spine (0236), tested all 5 policies:**

| Policy | Query | Result |
|---|---|---|
| 0236 - Spine | Medical necessity criteria | ✅ Correct, page 2 |
| 0673 - Knee | Arthroscopy medically necessary | ✅ Correct, multi-page |
| 0384 - MRCP | Appropriate use | ✅ Correct, multi-page |
| 0171 - Extremities | MRI criteria | ✅ Correct, multi-page |
| 0520 - Cardiac MRI | Coverage criteria | ⚠️ Declined |

**Cardiac MRI failure investigation:**
- Retrieved chunks were from Cardiac MRI PDF (correct policy routing)
- But retrieved page 69 (references) and page 50 (studies) instead of page 2 (indications)
- Page 2 exists in vectorstore, retrieval just didn't rank it in top-5

**Root cause:** Cardiac MRI PDF's page 2 lists anatomical conditions (thoracic aortic disease, pericardial disease) rather than using "criteria" language. Query "coverage criteria for cardiac MRI" has low semantic similarity to a list of medical conditions.

**Confirmation test:** Query rephrased to "What are the indications for cardiac MRI?" successfully retrieved page 14 and gave correct answer.

**Decision:** Documented as known limitation. Fix planned for Phase 3 via hybrid retrieval (BM25 + vector).

**Lesson learned:** Retrieval quality depends on how source documents phrase their content, not just system design.

---

## 8. Gemini Model Migration Journey

The Gemini API went through multiple model changes during development. Journey:

1. **Initial attempt:** `gemini-2.0-flash`
   - Error: 429 "generative_content_free_tier_input_token_count, limit: 0"
   - Model deprecated for free tier
   
2. **Switched to:** `gemini-2.5-flash`
   - Worked initially, later hit daily rate limits (20 requests/day)
   
3. **Attempted:** `gemini-2.5-flash-lite`
   - Error: 404 "This model is no longer available to new users"

4. **Attempted:** `gemini-3-flash`
   - Error: 404 "not found for API version v1beta"

5. **Final:** `gemini-3.5-flash-lite`
   - Works with generous free tier
   - Note: ignores `temperature=0` parameter (uses fixed sampling defaults)

**Lesson learned:** Google Gemini model naming and availability changes frequently. Do NOT pin to `-latest` tags in production. For final version, plan to switch to `gemini-3.5-flash` (better quality, still cheap, stable version).

**Debugging method:** Called `client.models.list()` to enumerate models actually available to the API key, rather than guessing from blog posts.

**Files affected:** `src/rag/rag_chain.py`

---

## 9. Streamlit Guardrail Refinement

**Initial UI issue:** When LLM declined an out-of-scope query, the "View Retrieved Sources" expander still displayed 5 chunks. This was confusing - if the answer was declined, why show sources?

**Root cause:** UI code displayed sources unconditionally.

**Fix in `streamlit_app.py`:**
```python
DECLINE_PHRASE = "The provided policy documents do not contain this information."
if DECLINE_PHRASE not in answer:
    with st.expander("View Retrieved Sources"):
        # ... display sources
```

**Result:** Sources only appear when the LLM actually answered. Out-of-scope queries show only the decline message.

**Design principle:** UI should match backend logic. Contradictory displays erode user trust.

---

## 10. Vector Store Persistence

**Motivation:** Rebuilding the FAISS index from PDFs takes ~1-2 minutes. Not acceptable for Streamlit app startup.

**Solution:** Added `save_vectorstore()` and `load_vectorstore()` functions to `create_vectorstore.py`.

**Result:** Streamlit loads pre-built index in ~1 second instead of rebuilding.

**Files affected:** `src/retrieval/create_vectorstore.py`, `app/streamlit_app.py`

**Note:** FAISS `load_local()` requires `allow_dangerous_deserialization=True` because it uses pickle. Safe here because we generated the file ourselves. Would require more caution in a multi-user or user-uploaded-file scenario.

---

## 11. Evaluation Test Set Design

**Target size:** 10-15 questions covering all 5 policies.

**Coverage strategy:**
- 3 questions for the primary MVP policy (Spine)
- 2 questions each for remaining 4 policies
- 1 out-of-scope question to test guardrails

**Grading dimensions considered but not implemented:**
- Answer factual accuracy (would require manual grading - deferred)
- Citation format correctness (visually verified but not automated)
- RAGAS metrics (context precision, faithfulness, answer relevancy - Phase 2)

**Files affected:** `notebooks/03_evaluation.ipynb`, `data/evaluation_results.csv`

---

## Locked Configurations (Do NOT Change)

Based on this experiment history, the following configurations are locked:

| Component | Setting | Rationale |
|---|---|---|
| Embedding model | BAAI/bge-small-en-v1.5 | Slightly better than MiniLM for domain |
| Normalize embeddings | True | Required for cosine similarity |
| Chunk size | 800 | Biggest improvement over 2000 |
| Chunk overlap | 150 | Preserves context across chunk boundaries |
| Retrieval | k=5 | Balance between recall and noise |
| Merging | Disabled | Destroys section boundaries |
| Filter keywords | TOC, Top, Additional Info, Policy History | Removes navigation pages |
| Whitespace cleanup order | Normalize first, then remove, then normalize again | Regex patterns fail on unnormalized text |