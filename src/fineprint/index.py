import bm25s
from bm25s import BM25

def get_bm25_retriever():
    retriever = bm25s.BM25()
    return retriever

def index_corpus_with_bm25(corpus: list[str]):
    corpus_tokens = bm25s.tokenize(corpus)
    retriever = get_bm25_retriever()
    retriever.index(corpus_tokens)
    return retriever

def query_bm25(query: str, retriever: BM25):
    query_tokens = bm25s.tokenize(query)
    [doc_indices], scores = retriever.retrieve(query_tokens, k=5)
    return doc_indices.tolist(), scores


if __name__ == "__main__":

    from fineprint.chunk import split_on_headings
    from fineprint.convert import get_or_create_markdown
    
    md_text = get_or_create_markdown(raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md")
    chunks = split_on_headings(md_text)

    retriever = index_corpus_with_bm25(chunks)
    indices, scores = query_bm25(query="moratorium period", retriever=retriever)
    
    
    print(indices)


    