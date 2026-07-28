import re
from langchain_core.documents import Document


def clean_text(text):
    
    # Normalize ALL whitespace first (handles \n, \xa0, tabs, multiple spaces)
    text = re.sub(r'\s+', ' ', text)

    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove dates
    text = re.sub(r'\d{1,2}/\d{1,2}/\d{4}', '', text)

    # Remove page markers like 1/60
    text = re.sub(r'\b\d+/\d+\b', '', text)

    # Remove timestamps like 00:48
    text = re.sub(r'\b\d{2}:\d{2}\b', '', text)

    # Remove arrows
    text = text.replace("-->", "")

    # Remove orphaned footer sentence
    text = re.sub(
        r'to see if precertification is required\.',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Final whitespace cleanup after removals
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def clean_documents(documents):
    
    cleaned_documents = []

    for doc in documents:
        cleaned_text = clean_text(doc.page_content)

        if len(cleaned_text) > 100:
            cleaned_documents.append(
                Document(
                    page_content=cleaned_text,
                    metadata=doc.metadata
                )
            )

    return cleaned_documents