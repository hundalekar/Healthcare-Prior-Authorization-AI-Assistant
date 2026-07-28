import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import os
import streamlit as st
from dotenv import load_dotenv

from src.retrieval.create_vectorstore import load_vectorstore
from src.rag.rag_chain import build_rag_chain

# Load environment variables
load_dotenv(dotenv_path=project_root / ".env")


# Page config
st.set_page_config(
    page_title="Healthcare Prior Authorization Assistant",
    page_icon="🏥",
    layout="wide"
)


# Cache the vectorstore and RAG chain so they load only once
@st.cache_resource
def get_rag_chain():
    """Load vectorstore and build RAG chain (cached)."""
    vectorstore_path = project_root / "data" / "processed" / "faiss_index"
    vectorstore = load_vectorstore(str(vectorstore_path))
    rag_chain = build_rag_chain(vectorstore)
    return rag_chain, vectorstore


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


# Load RAG chain (with loading spinner)
with st.spinner("Loading knowledge base..."):
    rag_chain, vectorstore = get_rag_chain()

st.success(f"Knowledge base loaded: {vectorstore.index.ntotal} indexed chunks from 5 policies")


# Query input
query = st.text_input(
    "Ask a question:",
    value=st.session_state.get("query", ""),
    placeholder="e.g., What are the criteria for MRI of the spine?"
)


# Answer section
if query:
    with st.spinner("Searching policies and generating answer..."):
        try:
            retrieved_docs = vectorstore.similarity_search(query, k=5)
            answer = rag_chain.invoke(query)
            
            st.subheader("Answer")
            st.markdown(answer)
            
            # Only show sources if the model actually answered
            DECLINE_PHRASE = "The provided policy documents do not contain this information."
            if DECLINE_PHRASE not in answer:
                with st.expander("View Retrieved Sources"):
                    for i, doc in enumerate(retrieved_docs):
                        meta = doc.metadata
                        st.markdown(
                            f"**Source {i+1}:** {meta['payer']}, "
                            f"Policy {meta['policy_number']} "
                            f"({meta['procedure']}), Page {meta['page']}"
                        )
                        st.text(doc.page_content[:400] + "...")
                        st.markdown("---")
        
        except Exception as e:
            st.error(f"Error: {e}")


# Footer
st.markdown("---")
st.caption(
    "**Disclaimer:** This is a portfolio project. Not for clinical use. "
    "Answers are based on Aetna Clinical Policy Bulletins available at the time of indexing."
)