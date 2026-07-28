import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from src.rag.retriever import get_retriever
from src.rag.prompt import prompt

load_dotenv()


def format_docs(docs):
    """Format retrieved docs into context string with citations."""
    formatted = []
    for doc in docs:
        text = doc.page_content
        meta = doc.metadata
        citation = (
            f"[Payer: {meta['payer']} | "
            f"Policy: {meta['policy_number']} | "
            f"Procedure: {meta['procedure']} | "
            f"Page: {meta['page']}]"
        )
        formatted.append(f"{text}\n{citation}")
    return "\n\n---\n\n".join(formatted)

#def build_rag_chain(vectorstore, k=5, model="gemini-flash-latest", temperature=0):
def build_rag_chain(vectorstore, k=5, model="gemini-3.5-flash-lite", temperature=0):
    """
    Build end-to-end RAG chain.
    
    Args:
        vectorstore: FAISS vectorstore
        k: number of chunks to retrieve
        model: Gemini model name
        temperature: 0 for factual answers (no creativity)
    
    Returns:
        RAG chain object
    """
    retriever = get_retriever(vectorstore, k=k)
    
    llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    rag_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain