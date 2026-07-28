from langchain_core.documents import Document


def merge_documents(documents, pages_per_chunk=5):

    merged_documents = []

    for i in range(0, len(documents), pages_per_chunk):

        batch = documents[i:i + pages_per_chunk]

        combined_text = "\n".join(
            doc.page_content for doc in batch
        )

        metadata = batch[0].metadata.copy()

        metadata["page_range"] = (
            f"{batch[0].metadata['page']}-"
            f"{batch[-1].metadata['page']}"
        )

        merged_documents.append(
            Document(
                page_content=combined_text,
                metadata=metadata
            )
        )

    return merged_documents