# fineprint-engine

A RAG engine over Indian health insurance policy wordings. Answers cite the clause they come from and say so when the policy is silent.

**Status: early.** A walking skeleton runs end to end on one policy. Each stage is deliberately crude and gets replaced one at a time, measured against an eval set. The roadmap below is the plan, not a claim.

## Why this domain

- Policy wordings are public, versioned PDFs with numbered clauses, so answers can be checked against the text
- The answer to most questions sits in one clause, a table or an exclusion, and the costly mistakes are the hidden ones: room-rent caps, co-pays, waiting periods
- One person with one PDF is better served by uploading it to a chat model. This engine is for the whole market: every insurer's wordings, every version, more than fits in a context window

## How it works today

1. PDF to markdown with PyMuPDF4LLM, cached per document
2. Chunks split on clause headings and numbered sub-clauses (`- 5.2.3.`), each tagged with its clause id, the policy's UIN and its heading path rebuilt from the clause number (e.g. `5 Exclusions > 5.2 Specific Exclusions > 5.2.2 ...`)
3. Hybrid retrieval: BM25 (`bm25s`) and dense vectors (`bge-small-en-v1.5`), merged with reciprocal rank fusion (k = 60)
4. An LLM (`gpt-oss-120b` via OpenRouter) answers only from the retrieved clauses, with structured output: the answer, its citations as (UIN, clause id) pairs, and a flag for when the clauses don't answer the question

Asked "What is the moratorium period in this policy?", it answers 60 months and cites clause 6.1.10.

## What's been measured

- [PDF converter benchmark](docs/benchmarks/pdf-converters.md): Docling, PyMuPDF4LLM and MarkItDown on 9 wordings from 3 insurers. Docling dropped table text, MarkItDown interleaved two-column pages, PyMuPDF4LLM lost no text. Decision in [ADR 001](docs/adr/001-pdf-converter.md)
- First failures found by running the skeleton: a citation quoted an insurer's plain-language sidebar as if it were clause text, and "not in the retrieved clauses" was turned into "the policy does not cover it"

### Eval runs, one change at a time

10 questions on ReAssure 2.0 (`evals/questions.json`), one run per question per change. The citation check counts how many cited clauses were among the retrieved ones. The same question can answer and cite differently between runs, so a difference of one or two citations is noise.

1. **Baseline** (2026-10-25): chunks split on headings, labelled with clause id and UIN, structured output
   - Citation check: 17 of 20 point to a retrieved clause, 2 don't, 1 names no clause. The 2 misses: an invented id, and a sub-clause (5.2.3) whose text sat inside its neighbour's chunk (5.2.2)
   - Clubfoot answered "covered", citing 5.2.3, which is an exclusion. The chunk it read didn't carry its parent heading, "Specific Exclusions"
2. **Heading paths in the label** (2026-10-25): each chunk's label carries its heading path, rebuilt from clause numbers
   - Better: clubfoot comes back "not covered", citing 5.2.3, in 4 of 5 runs. The fifth broke off mid-answer into repeated quote marks
   - Citation check: 15 of 18 point to a retrieved clause, 2 don't, 1 names no clause. Both misses are real sub-clauses (2.1.6, 5.2.3) whose text sat inside a retrieved chunk under its parent's label, so there was no label to cite
   - The "documents answer the question" flag isn't reliable: on clubfoot it was False in 3 of the 4 answers that said "not covered"
3. **Sub-clause chunks** (2026-10-26): numbered bullets start their own chunk, so chunks with a clause id went from 71 to 136
   - Better: citation check 10 of 14 point to a retrieved clause, none don't, 4 name no clause. No citation falls outside the retrieved set
   - Worse: clubfoot is wrong again, "not listed as excluded, treated as pre-existing". Retrieval missed 5.2.3: it ranks 56th in BM25 and 23rd in vectors, and each retriever passes on only its top 5. The question says "club foot from birth", the clause says "congenital anomaly", and the 120-character chunk shares only "treatment" with the question. The old 5.2.2 chunk held several exclusions and matched on more words
   - Wrong in a way the check can't see: OPD Treatment is cited as 2.1.32. Its own number (2.1.33) was lost in PDF conversion, so its text sits inside 2.1.32

So far each fix has moved the failure one stage earlier: from reading the clause, to citing it, to retrieving it. Smaller chunks bought exact citations and cost recall on questions worded differently from the policy. Next: a wider candidate pool (top 20 to 30 per retriever) with cross-encoder re-ranking, measured on the same 10

## Roadmap

- [x] Walking skeleton: convert, chunk, BM25 + vectors, RRF, cited answer
- [ ] Eval set: questions with the clause each answer should cite, including ones the policy is silent on
- [ ] Clean-up per insurer template (page headers and footers, sidebars, heading hierarchy rebuilt from clause numbers) and a check that flags documents whose headings don't match the clause list
- [ ] Parent-child chunks for long sections like Definitions
- [ ] Cross-encoder re-ranking, measured against the eval set
- [ ] Input guardrails: filters extracted into a schema, grounded in the question, a clarifying question when a filter can't be grounded
- [x] Citation check, measured on the eval set: a cited clause must be one of the retrieved clauses
- [ ] Citation check at answer time: a citation outside the retrieved set is dropped or flagged before the answer goes out
- [ ] Prompt-injection test: an instruction hidden in a policy PDF must not be followed
- [ ] PII redaction for a user's uploaded policy schedule: names, ages, policy and ID numbers swapped for placeholders before any LLM call, restored in the answer
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
