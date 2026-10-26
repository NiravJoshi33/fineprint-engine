from fineprint.chunk import split_on_headings
from fineprint.convert import get_or_create_markdown
from fineprint.eval import LLMAnswer
from fineprint.index import index_corpus_with_bm25, query_bm25
from fineprint.llm import get_answer
from fineprint.rerank import rerank_docs
from fineprint.rrf import join_documents_with_rrf
from fineprint.vectors import get_embeddings, vector_search

md_text = get_or_create_markdown(
    raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md"
)
chunks = split_on_headings(md_text, "NBHHLIP27054V032627")
chunk_texts = [chunk["chunk"] for chunk in chunks]

# both indexes are built once and reused for every query
retriever = index_corpus_with_bm25(chunk_texts)
corpus_embeddings = get_embeddings(corpus=chunk_texts)


def get_answer_for_query(query: str):

    indices, _ = query_bm25(query=query, retriever=retriever, top_k=30)

    doc_indices = vector_search(
        query=query, corpus_embeddings=corpus_embeddings, top_k=30
    )

    joined_docs_indices = join_documents_with_rrf(
        bm25docs_indices=indices, vector_docs_indices=doc_indices
    )
    docs = [chunks[i] for i in joined_docs_indices]

    reranked_doc_indices = rerank_docs(query, [doc["chunk"] for doc in docs], 15)
    reranked_docs = [docs[i] for i in reranked_doc_indices]

    answer = get_answer(query=query, documents=reranked_docs)
    return answer, reranked_docs


if __name__ == "__main__":
    import json

    run_file = "data/runs/2026-10-26_bge_reranker_base_top15.jsonl"

    questions = []

    with open("evals/questions.json") as file:
        questions.extend(json.load(file))

    for data in questions:
        query = data["query"]
        print(f"processing query: {query}...")
        answer, docs = get_answer_for_query(query)
        parsed = LLMAnswer.model_validate_json(answer)
        new_result = {
            "q_id": data["id"],
            "query": query,
            "answer": parsed.answer,
            "citations": [citation.model_dump() for citation in parsed.citation],
            "docs_answer_query": parsed.documents_answer_query,
            "retrieved_docs": [
                {"uin": doc["policy_id"], "clause_id": doc["clause_id"]} for doc in docs
            ],
        }

        with open(run_file, "a") as file:
            file.write(json.dumps(new_result) + "\n")

    def validate_citations():
        null_citations = 0
        total_matching = 0
        total_cited = 0
        with open(run_file, "r") as file:
            for item in file:
                eval_data = json.loads(item)

                cited_clauses = eval_data["citations"]
                retrieved_clauses = eval_data["retrieved_docs"]

                matched_clauses = []
                for clause in cited_clauses:
                    if clause["clause_id"] is None or clause["clause_id"] == "":
                        null_citations += 1
                    elif clause in retrieved_clauses:
                        matched_clauses.append(clause)

                print(f"question id: {eval_data['q_id']}")
                print(
                    f"number of cited clauses in retrieved clauses: {len(matched_clauses)} out of total {len(cited_clauses)} cited clauses"
                )
                total_matching += len(matched_clauses)
                total_cited += len(cited_clauses)

        print(f"null or empty citations: {null_citations}")
        print(
            f"total {total_matching} cited clauses came from retrieved docs from {total_cited}"
        )
        print(
            f"{total_cited - total_matching - null_citations} clauses were not found in retrieved docs"
        )

    validate_citations()
