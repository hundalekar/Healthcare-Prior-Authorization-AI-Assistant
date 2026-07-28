# Evaluation Results

This document presents the evaluation methodology, metrics, and findings for the Healthcare Prior Authorization AI Assistant.

---

## Methodology

A test set of 12 questions was created to evaluate the system across three dimensions:

1. **Policy Routing Accuracy** - Did the retriever surface chunks from the correct payer policy?
2. **Page Retrieval@5** - Did the top-5 retrieved chunks include the expected policy page?
3. **Decline Behavior** - Did the LLM correctly decline out-of-scope queries?

Each test question specifies:
- The natural language query
- The expected policy number (or "DECLINE" for out-of-scope)
- The expected page number(s) containing the answer

---

## Test Set Composition

| Policy | Coverage | Questions |
|---|---|---|
| CPB 0236 - MRI & CT Spine | 3 |
| CPB 0673 - Knee Arthroscopy | 2 |
| CPB 0520 - Cardiac MRI | 2 |
| CPB 0384 - MRCP | 2 |
| CPB 0171 - MRI Extremities | 2 |
| Out-of-scope (Medicare) | 1 |
| **Total** | **12** |

---

## Summary Metrics

| Metric | Score |
|---|---|
| Policy Routing Accuracy (top-5) | **100.0%** (11/11) |
| Page Retrieval@5 | 72.7% (8/11) |
| In-scope Answer Rate | 81.8% (9/11) |
| Out-of-scope Decline Rate | **100.0%** (1/1) |
| Overall Expected Behavior | 83.3% (10/12) |
| **Hallucination Rate** | **0.0%** (0/12) |

**Key finding:** Zero hallucinations across all 12 queries. All 2 failures were "conservative declines" - the LLM correctly refused to answer when retrieval missed the target page, rather than inventing an answer.

---

## Per-Question Breakdown

| # | Query | Expected | Policy in Top-5 | Page in Top-5 | Declined | Pass |
|---|---|---|---|---|---|---|
| 1 | Medical necessity criteria for MRI of the spine | 0236, p2 | ✅ | ✅ | No | ✅ |
| 2 | When is dynamic-kinetic MRI experimental | 0236, p3 | ✅ | ❌ | Yes | ❌ |
| 3 | When is MRI not medically necessary for spine trauma | 0236, p3/7 | ✅ | ❌ | Yes | ❌ |
| 4 | When is knee arthroscopy medically necessary | 0673, p2/3 | ✅ | ✅ | No | ✅ |
| 5 | Criteria for meniscal repair | 0673, p2-4 | ✅ | ✅ | No | ✅ |
| 6 | Indications for cardiac MRI | 0520, p2/3/14 | ✅ | ✅ | No | ✅ |
| 7 | Cardiac MRI for pericardial disease | 0520, p2/3 | ✅ | ❌ | No | ✅ |
| 8 | When is MRCP appropriate for PSC | 0384, p14/31 | ✅ | ✅ | No | ✅ |
| 9 | Role of MRCP versus ERCP | 0384, p14/31 | ✅ | ✅ | No | ✅ |
| 10 | Criteria for MRI of extremities | 0171, p2/3 | ✅ | ✅ | No | ✅ |
| 11 | MRI for diabetic foot ulcer | 0171, p3 | ✅ | ✅ | No | ✅ |
| 12 | Does Medicare cover MRI of the spine | DECLINE | N/A | N/A | Yes | ✅ |

---

## Failure Analysis

Two in-scope queries returned "The provided policy documents do not contain this information" despite the answer existing in the source documents. Both failures are from the same policy (CPB 0236).

### Failure 1: "When is dynamic-kinetic MRI considered experimental?"

- **Expected page:** 3
- **Retrieved pages (top-5):** 18, 18, 19 (Extremities), 63 (Cardiac), 33 (Extremities)
- **Root cause:** Page 3 was NOT retrieved. Page 18 contains related experimental content but not dynamic-kinetic MRI specifically. LLM correctly declined given the retrieved context.

### Failure 2: "When is MRI not medically necessary for spine trauma?"

- **Expected pages:** 3 or 7
- **Retrieved pages (top-5):** 2, 44, 14, 11, 41 (all Spine policy)
- **Root cause:** Neither page 3 nor page 7 was retrieved. The retriever found other Spine chunks but not the trauma-specific content. LLM correctly declined.

### Common pattern

Both failures share the same root cause: **the retriever missed the target page for query phrasings that used different terminology than the source document.** This aligns with the earlier Cardiac MRI wording sensitivity issue.

**Safety implication:** The LLM's declines are actually correct behavior. When retrieval fails, declining is safer than hallucinating an answer for a healthcare workflow.

---

## Comparison: Chunk Size Experiment

Before finalizing chunk_size=800, an earlier experiment used chunk_size=2000 with overlap=300.

**Query tested:** "What are the medical necessity criteria for MRI of the spine?"

| Chunk Size | Result 1 | Result 2 | Result 3 | Verdict |
|---|---|---|---|---|
| 2000/300 | Page 7 (background) | Page 2 (target) | Page 51 (refs) | Wrong page ranked #1 |
| 800/150 | **Page 2 (target)** | Page 11 (context) | Page 3 (related) | Correct page ranked #1 |

Reducing chunk size moved the correct page from rank #2 to rank #1 and eliminated reference/background pages from the top-3.

---

## Comparison: Embedding Model Experiment

**Original model:** sentence-transformers/all-MiniLM-L6-v2 (384-dim)  
**Final model:** BAAI/bge-small-en-v1.5 (384-dim)

Both models produced correct policy routing. BGE-small provided marginally better ranking quality on domain-specific queries and matches the tech stack originally planned for this project.

---

## Interpretation

**What works well:**
- Perfect policy routing (100%) across 5 different payer policies
- Zero hallucinations even when retrieval fails
- Safe decline behavior for out-of-scope queries

**Known limitations:**
- Wording sensitivity: queries that phrase criteria differently than the source may fail retrieval
- Small test set (12 queries) - expansion planned for future iterations

**For production use:**
Hybrid retrieval (BM25 + vector) would likely resolve the 2 in-scope failures by adding lexical matching for domain-specific terminology. This is documented in the [Phase 3 roadmap](README.md#roadmap).

---

## Raw Data

Full evaluation results with retrieved page lists per query are available in `data/evaluation_results.csv`.

Evaluation script: `notebooks/03_evaluation.ipynb`.