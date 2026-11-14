from fineprint.chunk import split_on_headings
from fineprint.convert import get_or_create_markdown
from fineprint.eval import LLMAnswer
from fineprint.gateway import LLMGateway
from fineprint.index import index_corpus_with_bm25, query_bm25
from fineprint.llm import get_answer
from fineprint.rerank import rerank_docs
from fineprint.rrf import join_documents_with_rrf
from fineprint.vectors import get_embeddings, vector_search

gateway = LLMGateway()

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

    result = get_answer(
        query=query, documents=reranked_docs, gateway=gateway, pin="azure_foundry"
    )
    return result.parsed.answer, reranked_docs, result


if __name__ == "__main__":
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(
        description="Run the eval questions through the pipeline into a new run file."
    )
    parser.add_argument(
        "--run_file",
        type=str,
        required=True,
        help="New file, e.g. data/runs/2026-11-14_azure_gpt5mini.jsonl",
    )
    args = parser.parse_args()
    run_file = args.run_file

    # one file holds one run: appending to an existing file would mix two configs in it
    # (the old hardcoded path pointed at the 26 Oct gpt-oss run)
    if os.path.exists(run_file):
        parser.error(f"{run_file} already exists, pick a new name")

    questions = []

    with open("evals/questions.json") as file:
        questions.extend(json.load(file))

    for data in questions:
        query = data["query"]
        print(f"processing query: {query}...")
        answer, docs, result = get_answer_for_query(query)
        new_result = {
            "q_id": data["id"],
            "query": query,
            "answer": answer,
            "citations": [citation.model_dump() for citation in result.parsed.citation],
            "docs_answer_query": result.parsed.documents_answer_query,
            "retrieved_docs": [
                {"uin": doc["policy_id"], "clause_id": doc["clause_id"]} for doc in docs
            ],
            "provider": result.provider,
            "model": result.model,
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
