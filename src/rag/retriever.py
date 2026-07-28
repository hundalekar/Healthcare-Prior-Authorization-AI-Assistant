from langchain_community.vectorstores import FAISS

def get_retriever(vectorstore, k=3):
    """
    Convert FAISS vectorstore into a retriever.
    
    Args:
        vectorstore: FAISS vectorstore object
        k: number of top chunks to retrieve (default 3)
    
    Returns:
        LangChain retriever object
    """
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )
    return retriever