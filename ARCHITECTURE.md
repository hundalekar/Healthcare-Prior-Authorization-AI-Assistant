# Architecture

This document describes the system architecture, design decisions, and component interactions for the Healthcare Prior Authorization AI Assistant.

---

## High-Level Data Flow

### Ingestion Pipeline (offline, one-time)

```
Aetna Policy PDFs (5)
        │
        ▼
PDF Ingestion (PyMuPDF)
        │
        ▼
Text Cleaning
  - Removes URLs, dates, timestamps
  - Removes footer artifacts, page markers
        │
        ▼
Filtering
  - Removes navigation pages (TOC, Policy History)
        │
        ▼
Chunking (RecursiveCharacterTextSplitter)
  - chunk_size=800, overlap=150
        │
        ▼
Embeddings (BAAI/bge-small-en-v1.5, 384-dim)
        │
        ▼
FAISS Index (1,351 vectors)
Persisted to: data/processed/faiss_index/
```

### Query Pipeline (per-request)

```
User Query (via Streamlit UI)
        │
        ▼
Retriever (FAISS similarity search, k=5)
        │
        ▼
Prompt Template
  - Injects retrieved context
  - Enforces grounding rules
        │
        ▼
LLM (Gemini 3.5 Flash-Lite)
        │
        ▼
Answer + Citations (displayed in Streamlit)
```

---

## Component Details

### 1. PDF Ingestion (`src/ingestion/load_documents.py`)

**Purpose:** Convert PDF files into LangChain Document objects with metadata.

**Design decisions:**
- **PyMuPDF (fitz)** over PyPDF2/pdfplumber: 3-5x faster, better handling of complex layouts, well-maintained
- **Metadata auto-assignment**: Filename keywords ("Spine", "Knee", "Cardiovascular") map to policy metadata dictionaries. Avoids hardcoding paths per file.
- **Length filter (>100 chars)**: Skips near-empty pages during initial extraction

**Metadata schema:**
```json
{
  "payer": "Aetna",
  "policy_number": "0236",
  "procedure": "MRI and CT Spine",
  "source": "<pdf_filename>.pdf",
  "page": 2
}
```

### 2. Text Cleaning (`src/ingestion/clean_documents.py`)

**Purpose:** Normalize whitespace and remove noise that would degrade embeddings.

**What gets removed:**
- URLs
- Date patterns (MM/DD/YYYY)
- Page markers (1/60, 2/60)
- Timestamps (00:48)
- Arrow artifacts (-->)
- Footer text ("to see if precertification is required.")

**Critical order:** Whitespace normalization runs FIRST to handle `\n`, `\xa0`, tabs before other regex patterns.

### 3. Filtering (`filter_documents()` in notebook)

**Purpose:** Remove non-content navigation pages.

**Removed if page contains:**
- "Table Of Contents"
- "Top"
- "Additional Information"
- "Policy History"

**Result:** 385 pages → 346 useful pages (~10% reduction).

### 4. Chunking (`src/ingestion/chunk_documents.py`)

**Configuration:**
- `chunk_size=800`
- `chunk_overlap=150`
- Separators: `["\n\n", "\n", ". ", " ", ""]`

**Why 800/150?**
Original attempt used 2000/300. Retrieval failed - the Medical Necessity section on page 2 was too diluted by surrounding text. Reducing to 800 with 150 overlap moved the correct page from rank #2 to rank #1. This was validated across multiple test queries.

### 5. Embeddings

**Model:** BAAI/bge-small-en-v1.5

**Why BGE over MiniLM?**
- Better retrieval quality on domain-specific text
- Same speed (both 384-dim)
- Normalized embeddings enable cosine similarity to work as inner product

**Normalization:** `normalize_embeddings=True` for consistent cosine similarity scoring.

### 6. Vector Store

**FAISS local index** with save/load persistence.

**Why FAISS over Chroma/Pinecone?**
- Zero dependencies beyond `faiss-cpu`
- Local, no external services required
- Fast for our scale (1,351 vectors)
- Easy to persist and reload
- Portfolio-friendly (works on any machine)

### 7. Retriever

**Similarity search, k=5**

**Why k=5?**
Tested k=3 (too narrow, missed relevant chunks) and k=7 (diminishing returns, more token cost). k=5 balanced recall against noise for policy documents that often span multiple pages.

### 8. Prompt Template (`src/rag/prompt.py`)

**Structure:**
1. Role definition: "healthcare prior authorization assistant"
2. STRICT RULES section (6 rules)
3. Context injection point
4. Question injection point

**Key rules:**
- Answer ONLY from provided context
- Decline if context lacks answer (specific decline phrase)
- No outside knowledge
- No medical advice
- Mandatory citation format

**Design decision:** Explicit decline phrase enables downstream logic to hide sources when the LLM declines - preventing confusing UI where a decline is shown alongside "sources."

### 9. LLM Integration (`src/rag/rag_chain.py`)

**Model:** Google Gemini 3.5 Flash-Lite

**Why Flash-Lite?**
- Free tier with generous limits (adequate for MVP)
- Sufficient quality for extraction + formatting tasks
- Task doesn't require complex reasoning (LLM just synthesizes retrieved context)

**Chain composition (LangChain LCEL):**
```python
{
    "context": retriever | format_docs,
    "question": RunnablePassthrough()
}
| prompt
| llm
| StrOutputParser()
```

### 10. Streamlit UI (`app/streamlit_app.py`)

**Features:**
- Cached vectorstore + RAG chain (loads once per session)
- Clickable sample questions in sidebar
- Query input with persistent state
- Formatted markdown answer display
- Expandable "Retrieved Sources" showing chunk metadata + preview text
- Guardrail logic: sources hidden when LLM declines

---

## Key Design Trade-offs

| Decision | Alternative | Why We Chose |
|---|---|---|
| Chunk 800/150 | Chunk 2000/300 | Better retrieval precision for policy documents |
| BGE-small | all-MiniLM-L6-v2 | Higher retrieval quality, same speed |
| FAISS local | Chroma/Pinecone | No external dependencies, portable |
| k=5 | k=3 or k=7 | Best balance of recall vs noise |
| No merging | Merge 5 pages | Preserved page boundaries in retrieval |
| Strict decline prompt | Loose grounding | Zero hallucinations for healthcare safety |

---

## What Happens on a Query

1. User types "What are the medical necessity criteria for MRI of the spine?" in Streamlit
2. Query is sent to FAISS retriever
3. Top-5 most similar chunks are retrieved
4. Chunks are formatted with citation metadata into a context string
5. Context + query + rules assembled into prompt
6. Prompt sent to Gemini API
7. Gemini returns grounded answer with citation
8. Streamlit displays answer
9. If answer is a decline, sources are hidden
10. Otherwise, sources are displayed in expandable section

**Latency:** ~2-4 seconds end-to-end (dominated by Gemini API call).

---

## Safety & Guardrails

The system implements a **defense-in-depth** approach to prevent hallucination:

1. **Prompt-level**: Strict rules require answers only from context, with an explicit decline phrase for out-of-scope queries
2. **Temperature=0**: Reduces LLM creativity (though Flash-Lite ignores this parameter)
3. **UI-level**: Sources hidden when LLM declines, preventing contradictory display
4. **Evaluation-level**: 12-query test set verified zero hallucinations

---

## Scaling Considerations

**Current scale:** 5 PDFs, 386 pages, 1,351 chunks. Fits comfortably in memory.

**To scale to 100+ PDFs:**
- FAISS handles millions of vectors easily
- Consider moving embedding generation to GPU
- Consider hybrid retrieval (BM25 + vector) - see Phase 3 roadmap
- Consider distributed vectorstore (e.g., Weaviate, Pinecone) if multi-user

**Bottleneck:** LLM latency, not retrieval. Batching queries or caching common ones would help.