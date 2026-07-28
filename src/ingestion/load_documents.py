import fitz
from pathlib import Path
from langchain_core.documents import Document

# Mapping of PDF filename patterns to metadata
POLICY_METADATA = {
    "Spine": {
        "policy_number": "0236",
        "procedure": "MRI and CT Spine"
    },
    "Knee": {
        "policy_number": "0673",
        "procedure": "Knee Arthroscopy / Osteoarthritis"
    },
    "Extremities": {
        "policy_number": "0171",
        "procedure": "MRI Extremities"
    },
    "Cardiovascular": {
        "policy_number": "0520",
        "procedure": "Cardiac MRI"
    },
    "Cholangiopancreatography": {
        "policy_number": "0384",
        "procedure": "MRCP"
    }
}


def get_policy_metadata(filename):
    """Match PDF filename to policy metadata."""
    for keyword, meta in POLICY_METADATA.items():
        if keyword in filename:
            return meta
    return {"policy_number": "Unknown", "procedure": "Unknown"}


def load_pdf(pdf_path):
    """
    Load a single PDF into LangChain Document objects.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        List of Document objects (one per page)
    """
    pdf_path = Path(pdf_path)
    policy_meta = get_policy_metadata(pdf_path.name)
    
    documents = []
    doc = fitz.open(pdf_path)
    
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if len(text.strip()) > 100:
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "payer": "Aetna",
                        "policy_number": policy_meta["policy_number"],
                        "procedure": policy_meta["procedure"],
                        "source": pdf_path.name,
                        "page": page_num + 1
                    }
                )
            )
    doc.close()
    return documents


def load_all_pdfs(pdf_folder):
    """
    Load all PDFs in a folder.
    
    Args:
        pdf_folder: Path to folder containing PDFs
    
    Returns:
        List of all Document objects across all PDFs
    """
    pdf_folder = Path(pdf_folder)
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    all_documents = []
    for pdf in pdf_files:
        docs = load_pdf(pdf)
        all_documents.extend(docs)
        print(f"Loaded {len(docs)} pages from {pdf.name}")
    
    print(f"\nTotal documents: {len(all_documents)}")
    return all_documents