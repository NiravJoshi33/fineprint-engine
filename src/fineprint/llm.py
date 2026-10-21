from openai import OpenAI
from os import getenv
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

llm_api_key = getenv("OPENROUTER_API_KEY")

if not llm_api_key:
    raise OSError("Environment Variable 'OPENROUTER_API_KEY' not set")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=llm_api_key
)

def get_answer(query: str, documents: list[str]):
    system_prompt = """
        Answer the query using only the provided documents from insurance policy and 
        cite the clause along with the answer. If documents don't cover the answer
        for the query, say so. 
    """

    user_prompt = f"""
        ## Query
        {query}
        
        ## Documents
        {"\n".join(documents)}
    """

    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

    return completion.choices[0].message.content


if __name__ == "__main__":
    from fineprint.chunk import split_on_headings
    from fineprint.convert import get_or_create_markdown
    from fineprint.index import index_corpus_with_bm25, query_bm25
    from fineprint.vectors import vector_search, get_embeddings
    from fineprint.rrf import join_documents_with_rrf

    
    md_text = get_or_create_markdown(raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md")
    chunks = split_on_headings(md_text)
    retriever = index_corpus_with_bm25(chunks)

    def get_answer_for_query(query: str):

        
        indices, scores = query_bm25(query=query, retriever=retriever)

        corpus_embeddings = get_embeddings(corpus=chunks)
        doc_indices = vector_search(query=query, corpus_embeddings=corpus_embeddings, corpus=chunks, top_k=5)

        joined_docs_indices = join_documents_with_rrf(bm25docs_indices=indices, vector_docs_indices=doc_indices)
        docs = [chunks[i] for i in joined_docs_indices]

        answer = get_answer(query=query, documents=docs)
        return answer
    

    answer = get_answer_for_query(query="What is the moratorium period in this policy?")
    answer2 = get_answer_for_query(query="Does this policy cover my pet dog?")

    print(f"answer: {answer}")
    print(f"answer 2: {answer2}")