from sentence_transformers import CrossEncoder

model = CrossEncoder(model_name_or_path="BAAI/bge-reranker-base")


def rerank_docs(query: str, docs: list, top_k: int = 10):
    rank_results = model.rank(query=query, documents=docs, top_k=top_k)

    return [result["corpus_id"] for result in rank_results]
