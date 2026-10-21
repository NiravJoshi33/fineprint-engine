# fineprint-engine

A RAG engine over Indian health insurance policy wordings. Answers cite the clause they come from and say so when the policy is silent.

**Status: early.** A walking skeleton runs end to end on one policy. Each stage is deliberately crude and gets replaced one at a time, measured against an eval set. The roadmap below is the plan, not a claim.

## Why this domain

- Policy wordings are public, versioned PDFs with numbered clauses, so answers can be checked against the text
- The answer to most questions sits in one clause, a table or an exclusion, and the costly mistakes are the hidden ones: room-rent caps, co-pays, waiting periods
- One person with one PDF is better served by uploading it to a chat model. This engine is for the whole market: every insurer's wordings, every version, more than fits in a context window

## How it works today

1. PDF to markdown with PyMuPDF4LLM, cached per document
2. Chunks split on clause headings
3. Hybrid retrieval: BM25 (`bm25s`) and dense vectors (`bge-small-en-v1.5`), merged with reciprocal rank fusion (k = 60)
4. An LLM (`gpt-oss-120b` via OpenRouter) answers only from the retrieved clauses and cites them

Asked "What is the moratorium period in this policy?", it answers 60 months and cites clause 6.1.10.

## What's been measured

- [PDF converter benchmark](docs/benchmarks/pdf-converters.md): Docling, PyMuPDF4LLM and MarkItDown on 9 wordings from 3 insurers. Docling dropped table text, MarkItDown interleaved two-column pages, PyMuPDF4LLM lost no text. Decision in [ADR 001](docs/adr/001-pdf-converter.md)
- First failures found by running the skeleton: a citation quoted an insurer's plain-language sidebar as if it were clause text, and "not in the retrieved clauses" was turned into "the policy does not cover it"

## Roadmap

- [x] Walking skeleton: convert, chunk, BM25 + vectors, RRF, cited answer
- [ ] Eval set: questions with the clause each answer should cite, including ones the policy is silent on
- [ ] Clean-up per insurer template (page headers and footers, sidebars, heading hierarchy rebuilt from clause numbers) and a check that flags documents whose headings don't match the clause list
- [ ] Parent-child chunks for long sections like Definitions
- [ ] Cross-encoder re-ranking, measured against the eval set
- [ ] Input guardrails: filters extracted into a schema, grounded in the question, a clarifying question when a filter can't be grounded
- [ ] Citation check: a cited clause must be one of the retrieved clauses
- [ ] Prompt-injection test: an instruction hidden in a policy PDF must not be followed
- [ ] Versioning: product lists, UINs, content hashes, section-level diffs between versions
- [ ] Deployed API with an eval report against a long-context baseline

## Running it

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
mkdir -p raw data
echo "OPENROUTER_API_KEY=..." > .env
uv run python -m fineprint.llm
```

Policy PDFs aren't included. Their redistribution terms haven't been checked, so `raw/` and `data/` are gitignored. The policy used so far is Niva Bupa's ReAssure 2.0 wording, from [Niva Bupa's download centre](https://transactions.nivabupa.com/pages/downloads.aspx). Save it as `raw/niva_reassure2.pdf`.

## License

MIT for this code. PyMuPDF and PyMuPDF4LLM, used for conversion, are AGPL-3.0.
