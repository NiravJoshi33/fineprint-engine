def join_documents_with_rrf(bm25docs_indices: list[int], vector_docs_indices: list[int], k: int = 60):
    all_indices = list(set(bm25docs_indices + vector_docs_indices))

    index_score_map = dict()

    for index in all_indices:
        score = 0
        if index in bm25docs_indices:
            # get the position of index
            index_pos = bm25docs_indices.index(index) + 1 # index method returns position starting from 0 but next equation needs starting with 1

            score += 1 / (k + index_pos)

        if index in vector_docs_indices:
            index_pos = vector_docs_indices.index(index) + 1

            score += 1 / (k + index_pos)

        index_score_map[index] = score

    return sorted(index_score_map, key=index_score_map.get, reverse=True)

    

if __name__ == "__main__":
    from fineprint.chunk import split_on_headings
    from fineprint.convert import get_or_create_markdown
    from fineprint.index import index_corpus_with_bm25, query_bm25
    from fineprint.vectors import vector_search, get_embeddings

    
    md_text = get_or_create_markdown(raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md")
    chunks = split_on_headings(md_text)

    retriever = index_corpus_with_bm25(chunks)
    indices, scores = query_bm25(query="moratorium period", retriever=retriever)

    corpus_embeddings = get_embeddings(corpus=chunks)
    doc_indices = vector_search(query="moratorium period", corpus_embeddings=corpus_embeddings, corpus=chunks, top_k=5)

    joined_docs_indices = join_documents_with_rrf(bm25docs_indices=indices, vector_docs_indices=doc_indices)
    print(joined_docs_indices)

        
