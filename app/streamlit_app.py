import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import os
import streamlit as st
from dotenv import load_dotenv
from src.retrieval.create_vectorstore import load_vectorstore
from src.rag.rag_chain import build_rag_chain, format_docs
from src.rag.prompt import prompt as rag_prompt
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables
load_dotenv(dotenv_path=project_root / ".env")

# Page config
st.set_page_config(
    page_title="Healthcare Prior Authorization Assistant",
    page_icon="🏥",
    layout="wide"
)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "query" not in st.session_state:
    st.session_state["query"] = ""
if "latest_result" not in st.session_state:
    st.session_state["latest_result"] = None

# Policy filter options
POLICY_OPTIONS = {
    "All Policies": None,
    "CPB 0236 - MRI & CT Spine": "0236",
    "CPB 0673 - Knee Arthroscopy": "0673",
    "CPB 0171 - MRI Extremities": "0171",
    "CPB 0520 - Cardiac MRI": "0520",
    "CPB 0384 - MRCP": "0384",
}

DECLINE_PHRASE = "The provided policy documents do not contain this information."


# Cache resources so they load only once
@st.cache_resource
def get_resources():
    """Load vectorstore, RAG chain, and LLM (cached)."""
    vectorstore_path = project_root / "data" / "processed" / "faiss_index"
    vectorstore = load_vectorstore(str(vectorstore_path))
    rag_chain = build_rag_chain(vectorstore)
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
    return rag_chain, vectorstore, llm


def filter_docs_by_policy(docs, policy_number):
    """Filter retrieved documents to a specific policy number."""
    if policy_number is None:
        return docs
    return [doc for doc in docs if doc.metadata.get("policy_number") == policy_number]


def process_query(query, selected_policy, rag_chain, vectorstore, llm):
    """Process a query and return answer + sources."""
    retrieved_docs = vectorstore.similarity_search(query, k=5)
    policy_number = POLICY_OPTIONS[selected_policy]
    filtered_docs = filter_docs_by_policy(retrieved_docs, policy_number)

    # Handle empty filter results
    if not filtered_docs and policy_number is not None:
        answer = (
            f"No relevant information found in {selected_policy}. "
            "Try selecting 'All Policies' or a different policy."
        )
        sources_data = []
    else:
        # Generate answer
        if policy_number is not None and filtered_docs:
            # Policy filter active - invoke with filtered context only
            context_str = format_docs(filtered_docs)
            chain = rag_prompt | llm | StrOutputParser()
            answer = chain.invoke({"context": context_str, "question": query})
        else:
            # All policies - use standard chain
            answer = rag_chain.invoke(query)
        if DECLINE_PHRASE in answer:
            answer = DECLINE_PHRASE

        # Build source data for display
        docs_for_display = filtered_docs if filtered_docs else retrieved_docs
        sources_data = []
        if DECLINE_PHRASE not in answer:
            for doc in docs_for_display:
                meta = doc.metadata
                sources_data.append({
                    "payer": meta["payer"],
                    "policy_number": meta["policy_number"],
                    "procedure": meta["procedure"],
                    "page": meta["page"],
                    "snippet": doc.page_content[:400] + "...",
                })

    return answer, sources_data


# Header
st.title("🏥 Healthcare Prior Authorization Assistant")
st.markdown(
    "Ask questions about **Aetna clinical policy requirements** for imaging procedures. "
    "Answers include citations to the source policy, page number, and payer."
)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown(
        "This assistant helps hospital staff find insurance policy requirements "
        "for prior authorization decisions."
    )

    st.subheader("Covered Policies")
    st.markdown(
        """
        - **CPB 0236** - MRI & CT Spine
        - **CPB 0673** - Knee Arthroscopy
        - **CPB 0171** - MRI Extremities
        - **CPB 0520** - Cardiac MRI
        - **CPB 0384** - MRCP
        """
    )

    # Policy filter dropdown
    st.subheader("Policy Filter")
    selected_policy = st.selectbox(
        "Scope search to a specific policy:",
        options=list(POLICY_OPTIONS.keys()),
        index=0,
    )

    st.subheader("Sample Questions")
    sample_questions = [
        "What are the medical necessity criteria for MRI of the spine?",
        "When is knee arthroscopy medically necessary?",
        "What are the indications for cardiac MRI?",
        "When is MRCP appropriate?",
        "Is dynamic-kinetic MRI covered by Aetna?"
    ]
    for sq in sample_questions:
        if st.button(sq, key=sq, use_container_width=True):
            st.session_state["query"] = sq
            st.session_state["sample_submitted"] = True

    st.markdown("---")

    # Clear/Reset button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state["chat_history"] = []
        st.session_state["query"] = ""
        st.session_state["latest_result"] = None
        st.rerun()

# Load resources (with loading spinner)
with st.spinner("Loading knowledge base..."):
    rag_chain, vectorstore, llm = get_resources()

st.success(f"Knowledge base loaded: {vectorstore.index.ntotal} indexed chunks from 5 policies")

# Display chat history (exclude latest - it shows in Answer section below)
history = st.session_state["chat_history"]
if len(history) > 1:
    st.subheader("Conversation")
    for idx, entry in enumerate(history[:-1]):
        with st.container():
            st.markdown(f"**Q:** {entry['question']}")
            st.markdown(f"**A:** {entry['answer']}")
            if entry.get("sources"):
                with st.expander(f"View Sources (Q{idx + 1})"):
                    for j, src in enumerate(entry["sources"]):
                        st.markdown(
                            f"**Source {j + 1}:** {src['payer']}, "
                            f"Policy {src['policy_number']} "
                            f"({src['procedure']}), Page {src['page']}"
                        )
                        st.text(src["snippet"])
                        st.markdown("---")
            st.markdown("---")

# Display latest result (persists across reruns)
if st.session_state["latest_result"]:
    result = st.session_state["latest_result"]
    st.markdown(f"**Q:** {result['question']}")
    st.markdown(f"**A:** {result['answer']}")

    # Show sources if available
    if result["sources"]:
        with st.expander("View Retrieved Sources"):
            for i, src in enumerate(result["sources"]):
                st.markdown(
                    f"**Source {i + 1}:** {src['payer']}, "
                    f"Policy {src['policy_number']} "
                    f"({src['procedure']}), Page {src['page']}"
                )
                st.text(src["snippet"])
                st.markdown("---")

# Query input with form at bottom (clear_on_submit empties the field after search)
with st.form("search_form", clear_on_submit=True):
    query_input = st.text_input(
        "Ask a question:",
        placeholder="e.g., What are the criteria for MRI of the spine?"
    )
    search_submitted = st.form_submit_button("🔍 Search Policies")

# Check if a sample question was clicked
sample_submitted = st.session_state.pop("sample_submitted", False)
should_process = search_submitted or sample_submitted
query_to_process = query_input if search_submitted else st.session_state.get("query", "")

# Process query only on explicit submit
if should_process and query_to_process:
    with st.spinner("🔍 Searching policies and generating answer..."):
        try:
            answer, sources_data = process_query(
                query_to_process, selected_policy, rag_chain, vectorstore, llm
            )

            # Save result
            result = {
                "question": query_to_process,
                "answer": answer,
                "sources": sources_data,
            }
            st.session_state["latest_result"] = result
            st.session_state["chat_history"].append(result)
            st.session_state["query"] = ""
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# Footer
st.markdown("---")
st.caption(
    "**Disclaimer:** This is a portfolio project. Not for clinical use. "
    "Answers are based on Aetna Clinical Policy Bulletins available at the time of indexing."
)