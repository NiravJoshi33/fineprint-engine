from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer(model_name_or_path="BAAI/bge-small-en-v1.5")

def get_embeddings(corpus: list[str]):
    return model.encode(corpus, normalize_embeddings=True)


def get_embeddings_for_query(query: str):
    return model.encode("Represent this sentence for searching relevant passages: " + query, normalize_embeddings=True)

def vector_search(query: str, corpus_embeddings: np.ndarray, corpus: list[str], top_k: int) -> list[int]:
    query_embeddings = get_embeddings_for_query(query=query)
    similarity = corpus_embeddings @ query_embeddings
    sorted_similarity_positions = np.argsort(similarity) # sorts positions into smallest to largest

    chunk_indices = []
    for i in range(top_k):
        chunk_index = sorted_similarity_positions[- i - 1]
        chunk_indices.append(chunk_index)

    return [n.item() for n in chunk_indices]

   

    

if __name__ == "__main__":
    from fineprint.chunk import split_on_headings
    from fineprint.convert import get_or_create_markdown
   
    
    md_text = get_or_create_markdown(raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md")
    chunks = split_on_headings(md_text)

    corpus_embeddings = get_embeddings(corpus=chunks)
    doc_indices = vector_search(query="moratorium period", corpus_embeddings=corpus_embeddings, corpus=chunks, top_k=5)
    

    