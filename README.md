# fineprint-engine

A RAG engine over Indian health insurance policy wordings. Answers cite the clause they come from and say so when the policy is silent.

**Status: early.** A walking skeleton runs end to end on one policy, deployed on AWS Lambda (see [Deployment](#deployment)). Each stage is deliberately crude and gets replaced one at a time, measured against an eval set. The roadmap below is the plan, not a claim.

## Why this domain

- Policy wordings are public, versioned PDFs with numbered clauses, so answers can be checked against the text
- The answer to most questions sits in one clause, a table or an exclusion, and the costly mistakes are the hidden ones: room-rent caps, co-pays, waiting periods
- One person with one PDF is better served by uploading it to a chat model. This engine is for the whole market: every insurer's wordings, every version, more than fits in a context window

## How it works today

1. PDF to markdown with PyMuPDF4LLM, cached per document
2. Chunks split on clause headings and numbered sub-clauses (`- 5.2.3.`), each tagged with its clause id, the policy's UIN and its heading path rebuilt from the clause number (e.g. `5 Exclusions > 5.2 Specific Exclusions > 5.2.2 ...`)
3. Hybrid retrieval: BM25 (`bm25s`) and dense vectors (`bge-small-en-v1.5`), merged with reciprocal rank fusion (k = 60)
4. An LLM (`deepseek-v4.1-flash` via OpenCode Go, set by `FINEPRINT_LLM_MODEL`; runs up to 26 Oct 2026 used `gpt-oss-120b` via OpenRouter) answers only from the retrieved clauses, with structured output: the answer, its citations as (UIN, clause id) pairs, and a flag for when the clauses don't answer the question

Asked "What is the moratorium period in this policy?", it answers 60 months and cites clause 6.1.10.

## What's been measured

- [PDF converter benchmark](docs/benchmarks/pdf-converters.md): Docling, PyMuPDF4LLM and MarkItDown on 9 wordings from 3 insurers. Docling dropped table text, MarkItDown interleaved two-column pages, PyMuPDF4LLM lost no text. Decision in [ADR 001](docs/adr/001-pdf-converter.md)
- First failures found by running the skeleton: a citation quoted an insurer's plain-language sidebar as if it were clause text, and "not in the retrieved clauses" was turned into "the policy does not cover it"

### Eval runs, one change at a time

10 questions on ReAssure 2.0 (`evals/questions.json`), one run per question per change, answered by `gpt-oss-120b`. The citation check counts how many cited clauses were among the retrieved ones. The same question can answer and cite differently between runs, so a difference of one or two citations is noise.

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

4. **Wider pool, MiniLM re-ranker** (2026-10-26): top 30 from each retriever (52 to 53 chunks after fusion), `cross-encoder/ms-marco-MiniLM-L6-v2` keeps the best 10
   - Better: clubfoot is right again. 5.2.3 rose from 43rd after fusion to 9th
   - Worse: the copay question lost both co-payment clauses. 4.19 fell from 10th to 26th (the vector search alone had it 1st) and 2.1.7 from 11th to 17th. With neither in front of it, the whole answer was the word "analysis"
   - Citation check: 10 of 12 point to a retrieved clause, none don't, 2 name no clause
   - Side run: all 53 fused chunks sent to the LLM with no re-ranking got clubfoot right in 2 of 2 runs. Once the clause is in front of it, the model reads it correctly
5. **bge-reranker-base instead of MiniLM** (2026-10-26): same pool, `BAAI/bge-reranker-base` keeps the best 10
   - Worse: both key clauses just miss the cut, 5.2.3 at 12th and 4.19 at 11th. Clubfoot is back to "pre-existing", and the copay answer says the policy only defines co-payment
   - Worse: one answer was a refusal ("I'm sorry, but I can't help with that"), and "can I add my parents" now says the documents don't mention it
   - Citation check: 10 of 16 point to a retrieved clause, none don't, 6 name no clause

6. **bge-reranker-base, keeping 15** (2026-10-26): same as 5, with the cut at 15 instead of 10
   - Better: clubfoot and copay both have their clauses in context. Copay is right, citing 4.19 and 2.1.7. Clubfoot reaches "not covered" via 5.2.3, and the reasoning mentions the heading path ("under Exclusions > Specific Exclusions")
   - Better: "are reports and diagnosis covered" now says they are when part of a covered hospitalisation, instead of a bare "No"
   - Worse: the clubfoot answer field holds the model's reasoning ("I need to produce output per instruction...") instead of an answer
   - Still wrong: "can I add my parents" says the documents don't mention it. The clause that answers it ranks 4th in vectors, 20th after fusion and 28th after re-ranking. BM25 misses it, likely because "add" doesn't match "Addition" without stemming
   - Citation check: 18 of 23 point to a retrieved clause, none don't, 5 name no clause

So far each fix has moved the failure one stage earlier: from reading the clause, to citing it, to retrieving it. Smaller chunks bought exact citations and cost recall on questions worded differently from the policy. Re-ranking with a cut of 15 gets clubfoot and copay right but loses "add my parents", which the narrow top-5 pool found. In several misses the vector search alone ranked the right clause higher than fusion or re-ranking did.

Four runs produced a broken answer (repeated quote marks, the single word "analysis", a refusal, reasoning in place of the answer), so the answer step needs a check of its own before anything ships

### The same changes on deepseek-v4.1-flash (2026-11-14)

Each change above was rebuilt from its commit in a separate git worktree with only the LLM swapped, then run three times. Retrieval doesn't involve the LLM, and every rebuild returned the same chunks as the gpt-oss run for every question, so the differences below come from the model. The baseline's label (clause id and UIN, no heading path) was never committed and was rebuilt by hand. Run files are `data/runs/2026-11-14_*_dsflash_r1..3.jsonl`.

Scored with `src/fineprint/grade.py` against `evals/answer_key.json`:

- Retrieved: the share of a question's expected clauses that were retrieved, averaged over the 9 questions that expect any. It doesn't depend on the model
- Cited: the same, counted against the answer's citations
- Flag: questions where "the documents answer the question" matches the key (True for the 7 answerable questions, False for the silent and out-of-scope ones)

| Change | Retrieved | Cited, gpt-oss (1 run) | Cited, deepseek (mean, range of 3) | Flag, gpt-oss | Flag, deepseek (range of 3) | Citation check, deepseek, 3 runs (in, out, no clause) |
|---|---|---|---|---|---|---|
| 1. Baseline | 0.19 | 0.19 | 0.16 (0.11 to 0.19) | 7/10 | 6 to 8 | 51, 5, 5 |
| 2. Heading paths | 0.19 | 0.25 | 0.15 (0.11 to 0.17) | 8/10 | 6 to 8 | 48, 9, 7 |
| 3. Sub-clause chunks | 0.22 | 0.19 | 0.16 (0.11 to 0.19) | 8/10 | 6 to 8 | 43, 0, 5 |
| 4. MiniLM, keep 10 | 0.33 | 0.17 | 0.26 (0.22 to 0.33) | 7/10 | 5 to 8 | 65, 0, 11 |
| 5. bge, keep 10 | 0.36 | 0.17 | 0.21 (0.06 to 0.31) | 6/10 | 5 to 7 | 45, 0, 5 |
| 6. bge, keep 15 | 0.53 | 0.33 | 0.43 (0.36 to 0.50) | 8/10 | 7 to 8 | 70, 0, 8 |
| Side run: all ~53 fused chunks | 0.73 | | 0.36 (0.23 to 0.51) | | 6 to 8 | 66, 0, 2 |

The gpt-oss side run covered 3 questions, so it has no comparable numbers.

- Three runs of one change move the cited score by up to 0.25 (change 5: 0.06 to 0.31) and the flag by up to 3 questions. A single run can't tell two changes apart by less than that, which covers most of the gpt-oss comparisons above. Keep 15 is the one clear winner: its worst run (0.36) beats the best run of changes 1 to 5
- Sub-clause chunks fixed citations on this model too. Changes 1 and 2 cited a clause outside the retrieved set 14 times in 6 runs, changes 3 to 6 and the side run 0 times in 15
- Clubfoot is never "not covered" in 21 runs. In all 15 runs where the exclusion text reached the model (changes 1, 2, 4, 6 and the side run), it quoted "treatment related to external Congenital Anomaly" as excluded, said the documents don't name club foot, and stopped. Twice it gave the reason in the system prompt's words: "I cannot conclude it is not covered." That line was added to stop "not retrieved" turning into "not covered". On this model it also blocks a correct "excluded", a step gpt-oss took in changes 2, 4 and 6. Without the exclusion in context (changes 3 and 5), all 6 answers took the pre-existing disease route, as gpt-oss did
- The MiniLM re-ranker lost both co-pay clauses here too. gpt-oss answered with the word "analysis". Deepseek said "the documents do not mention any copay" in all 3 runs, a wrong answer that reads like a right one. With keep 15, all 3 answers explain co-pay from 4.19 and 2.1.7
- "Can I add my parents" splits the same way as on gpt-oss. Changes 1 to 3 answered from the note that a new member can be added by endorsement or at renewal in all 9 runs, citing a null clause id because that note's chunk has none. Changes 4 to 6 said the documents don't say, in all 9
- No broken answers in the 180 for changes 1 to 6. With all ~53 chunks in context, 2 of 30 broke: one answer was only "DEDUCTIBLE/COPAY FOR ANY SCENARIO", one was empty
- 20 answers set the flag True but named their clauses only inside the answer text, with an empty citation list, so the cited score misses them. 24 more did the same with the flag False, which the schema asks for ("Empty when documents_answer_query is false"). That rule also hides what a hedged answer leaned on: several clubfoot answers quote the exclusion and cite nothing
- Calls took about 15 s at the median. A few stalled past the 120 s client timeout and went through on a retry

The order holds across both models: retrieval is still the bottleneck, and keep 15 is still the best setup. The next failure is different. With the exclusion in front of it, this model won't apply it to a condition the clause doesn't name, and the prompt's own rule is the likeliest reason.

### 7. Prompt without "Never conclude it is not covered" (2026-11-14)

Keep 15 on `deepseek-v4.1-flash`, three runs, with that one line removed from the system prompt. Retrieval is unchanged.

| | Line in (change 6) | Line out |
|---|---|---|
| Clubfoot | 0 of 3 apply the exclusion, all hedge | 3 of 3 apply it, citing 2.1.6 and 5.2.3 |
| ADHD (the silent question) | never "not covered" | never "not covered" |
| Cited | 0.43 (0.36 to 0.50) | 0.46 (0.39 to 0.50) |
| Flag | 8, 7, 7 | 8, 8, 8 |

- All three clubfoot answers now make the step from "external congenital anomaly" to club foot: "would be excluded", "would likely be excluded", "is not covered". Each still says the policy doesn't name club foot
- The line was there because "not in the retrieved clauses" kept turning into "not covered". The ADHD question is the only silent one in the set, so one question in three runs is thin evidence that the failure won't come back. More silent questions in the eval set would settle it
- Cited and flag moved by less than the noise between runs of one change

## Roadmap

- [x] Walking skeleton: convert, chunk, BM25 + vectors, RRF, cited answer
- [x] Eval set: questions with the clause each answer should cite, including ones the policy is silent on (`evals/answer_key.json`; 4 rows checked by hand against the wording, 6 by an AI agent, marked per row)
- [ ] Clean-up per insurer template (page headers and footers, sidebars, heading hierarchy rebuilt from clause numbers) and a check that flags documents whose headings don't match the clause list
- [ ] Parent-child chunks for long sections like Definitions
- [ ] Cross-encoder re-ranking, measured against the eval set
- [ ] Input guardrails: filters extracted into a schema, grounded in the question, a clarifying question when a filter can't be grounded
- [x] Citation check, measured on the eval set: a cited clause must be one of the retrieved clauses
- [x] Grader against the answer key (`src/fineprint/grade.py`): retrieved and cited hit rates per question, averaged over questions, and the "documents answer the question" flag checked against each question's type
- [ ] Citation check at answer time: a citation outside the retrieved set is dropped or flagged before the answer goes out
- [ ] Prompt-injection test: an instruction hidden in a policy PDF must not be followed
- [ ] PII redaction for a user's uploaded policy schedule: names, ages, policy and ID numbers swapped for placeholders before any LLM call, restored in the answer
- [ ] Versioning: product lists, UINs, content hashes, section-level diffs between versions
- [x] Deployed on AWS: Lambda from a container image, IAM-authenticated function URL, infrastructure in Terraform
- [ ] CI/CD: GitHub Actions deploys through OIDC, no AWS keys stored in GitHub
- [ ] Deployed API with an eval report against a long-context baseline

## Deployment

On AWS, all in Terraform (`infra/`):

- A Lambda function from a container image (`Dockerfile`, arm64): AWS's Python base image, CPU-only torch, and both models baked in, since Lambda's filesystem is read-only
- The image in ECR, tagged with the git commit it was built from
- An IAM execution role that can only write logs
- A function URL with `AWS_IAM` auth, so only requests signed with AWS credentials get in

Provider keys come from Terraform variables in a gitignored `.auto.tfvars`. Each stage logs its time to CloudWatch (`src/fineprint/timing.py`).

Measured on a new account, which is capped at 3,008 MB (2 vCPUs): a cold request takes about 90 s, mostly embedding the corpus at startup (24 s) and re-ranking 43 chunks (42 s). The same work takes about 2 s on an M-series Mac. Precomputing the embeddings into the image and sending the re-ranker fewer, shorter chunks are the next fixes.

Deploys run from GitHub Actions (`.github/workflows/deploy.yml`) on every push to `main` that changes what goes into the image:

- It signs in to AWS through OIDC, so no AWS keys are stored in GitHub. The role trusts only this repo's `main` and can only push to this ECR repo, update this one function and read the policy text
- It builds on an arm64 runner, pushes the image tagged with the commit and points the Lambda at it
- The policy text comes from a private S3 bucket, since `data/` isn't in git. Terraform uploads it; after changing it, run the workflow by hand
- Terraform creates the function, then leaves its image to the workflow. ECR keeps the last 3 images, so a rollback is `aws lambda update-function-code --image-uri` with an earlier tag

## Running it

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
mkdir -p raw data
echo "OPENCODE_API_KEY=..." > .env
uv run python -m fineprint.llm
```

Policy PDFs aren't included. Their redistribution terms haven't been checked, so `raw/` and `data/` are gitignored. The policy used so far is Niva Bupa's ReAssure 2.0 wording, from [Niva Bupa's download centre](https://transactions.nivabupa.com/pages/downloads.aspx). Save it as `raw/niva_reassure2.pdf`.

## License

MIT for this code. PyMuPDF and PyMuPDF4LLM, used for conversion, are AGPL-3.0.
