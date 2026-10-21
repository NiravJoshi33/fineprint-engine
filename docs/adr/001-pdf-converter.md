# 001 Convert PDFs to markdown with PyMuPDF4LLM

**Status:** Accepted
**Date:** 2026-10-20

## Context

All incoming documents (policy PDFs here) need converting into one format the chunker can split. That format is GitHub Flavored Markdown, because CommonMark has no tables and insurance terms live in tables. A converter has to meet four requirements:

- The same PDF gives the same markdown on every run. Version diffs depend on it
- No text is lost
- Tables survive
- Clause headings survive and no text moves to another clause. Chunking and citations depend on them

Two-column pages with sidebars, and a different layout and numbering scheme per insurer, are what make the conversion hard.

Docling, PyMuPDF4LLM and MarkItDown were picked for the benchmark on the requirements, popularity and project health. Results: [pdf-converters.md](../benchmarks/pdf-converters.md).

## Decision

Policy PDFs are converted with PyMuPDF4LLM 2.0 and PyMuPDF 2.0, pinned exactly (pymupdf-layout 2.0 is held by `uv.lock`). The versions are stored with each document's hash.

Two steps go with it:

- A clean-up step per insurer template: strip page headers and footers (read the UIN from them first), handle sidebars, rebuild the heading hierarchy from clause numbers
- A reference list of clause numbers, from the printed table of contents where there is one and from the PDF's text layer otherwise. If the markdown headings don't match it, the document is flagged for human review and not ingested

## Consequences

- **Easier:** no text was lost in 9 wordings from 3 insurers, tables come out usable, and conversion takes seconds per document
- **Harder:** the problems that remain (lost or demoted headings, sidebars cutting clauses, repeated headers and footers) need clean-up rules per insurer template. Every new insurer means new rules before its documents can be trusted, so the work grows with the corpus
- **License:** PyMuPDF and PyMuPDF4LLM are AGPL-3.0. If the engine runs as a network service, its source has to be offered to its users. Fineprint is open source, so that holds today
- **Revisit if:** a closed or commercial version is needed (a commercial license from Artifex, or another converter), OCR'd image pages turn out unreliable (Optima Wellbeing is mostly OCR, quality not checked yet), or an insurer's template keeps failing the reference check

## Alternatives considered

- **Docling (MIT):** dropped table cells and logged it, read numbered clauses as tables with rows shifted by one, and mixed sidebar text into clauses. Text loss can't be repaired after conversion, structure can
- **MarkItDown (MIT):** no headings at all, and on two-column pages it interleaves the clause and the sidebar line by line, so sentences from both are mixed
- **A vision model on every page:** not benchmarked. Possible later for pages the reference check flags, with the output stored by PDF hash so it's converted once
