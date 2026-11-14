from os import getenv
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI

from fineprint.eval import LLMAnswer
from fineprint.gateway import GatewayResult, LLMGateway, ProviderName

load_dotenv(dotenv_path=".env")

gateway = LLMGateway()


def format_document(chunk: dict) -> str:
    # the label is the only place the model can see the real ids, so citations copy them from here
    # an f-string turns None into the text "None", which the model then copies as a clause id
    clause_id = chunk["clause_id"] if chunk["clause_id"] is not None else "null"
    path = chunk["path"] if chunk["path"] is not None else "null"
    return f"[uin: {chunk['policy_id']} | clause_id: {clause_id}] | path: {path}\n{chunk['chunk']}"


def get_answer(
    query: str, documents: list[dict], gateway: LLMGateway, pin: ProviderName | None
) -> GatewayResult:
    # No "Never conclude it is not covered." line: it stopped deepseek-v4.1-flash from applying a
    # retrieved exclusion (clubfoot, 5.2.3) in all 15 runs where the exclusion text reached it. Taking it out fixed that without the
    # silent question turning into "not covered" (README, change 7, 3 runs: thin evidence)
    system_prompt = """
        Answer the query using only the provided documents from insurance policy and
        cite the clause along with the answer. If documents don't cover the answer
        for the query, say so.
        Cite only the uin and clause_id values shown in the document labels.
        If the documents don't mention something, say they don't mention it.
    """

    user_prompt = f"""
        ## Query
        {query}

        ## Documents
        {"\n\n".join(format_document(document) for document in documents)}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = gateway.ask_llm(messages, LLMAnswer, pin)

    return result


if __name__ == "__main__":
    from fineprint.chunk import split_on_headings
    from fineprint.convert import get_or_create_markdown
    from fineprint.index import index_corpus_with_bm25, query_bm25
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

        indices, _ = query_bm25(query=query, retriever=retriever)

        doc_indices = vector_search(
            query=query, corpus_embeddings=corpus_embeddings, top_k=5
        )

        joined_docs_indices = join_documents_with_rrf(
            bm25docs_indices=indices, vector_docs_indices=doc_indices
        )
        docs = [chunks[i] for i in joined_docs_indices]

        result = get_answer(query=query, documents=docs, gateway=gateway)
        return result.content

    answer = get_answer_for_query(query="What is the moratorium period in this policy?")
    answer2 = get_answer_for_query(query="Does this policy cover my pet dog?")

    print(f"answer: {(LLMAnswer.model_validate_json(answer))}")
    print(f"answer 2: {LLMAnswer.model_validate_json(answer2)}")
