from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings


def get_embedding_model():
    """Get the embedding model (single source of truth)."""
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={"normalize_embeddings": True}
    )


def create_vectorstore(chunks):
    """Create FAISS vectorstore from document chunks."""
    embedding_model = get_embedding_model()
    vectorstore = FAISS.from_documents(chunks, embedding_model)
    return vectorstore


def save_vectorstore(vectorstore, path):
    """Save FAISS vectorstore to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(path))
    print(f"Vectorstore saved to: {path}")


def load_vectorstore(path):
    """Load FAISS vectorstore from disk."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Vectorstore not found at: {path}")
    
    embedding_model = get_embedding_model()
    vectorstore = FAISS.load_local(
        str(path),
        embedding_model,
        allow_dangerous_deserialization=True
    )
    print(f"Vectorstore loaded from: {path}")
    return vectorstore