# PDF to markdown converters

Which converter turns Indian health insurance policy wordings into markdown the pipeline can chunk by clause.

## Requirements

1. The same PDF gives the same markdown on every run (hash compared over two runs)
2. Clause headings survive, so sections can be split on them
3. No text is lost or moved to the wrong clause
4. Tables survive, merged cells included

## Method

Each converter runs with its defaults on the same file. Clause numbers are pulled from the PDF's own text layer (`pdftotext -raw`) as the reference list, then checked against the converter's output. Failures were then read by eye against the PDF.

## Results

### Niva Bupa ReAssure 2.0 (UIN NBHHLIP27054V032627, 34 pages), 2026-10-20

| | Docling 2.140 | PyMuPDF4LLM | MarkItDown 0.1.8 |
|---|---|---|---|
| Same hash on two runs | yes | yes | yes |
| Headings | all at one level | all at one level, 2 lost | none |
| Text kept | 2 table cells dropped | all | all |
| Tables | clauses read as tables | good | broken |
| Two-column pages | sidebar text mixed into a clause | sidebars split clauses | columns interleaved line by line |
| License, time | MIT, about 40 s | AGPL-3.0, a few seconds | MIT, about 1 s |

Failures in detail:

- **Docling** read clauses 6.1.9 and 6.1.10, and 6.2.5 to 6.2.8, as two-column tables, with each row's text shifted by one line. It dropped one cell from each of two tables, and logged both drops as warnings. Sidebar text landed inside 6.1.8. Headings came out with `&amp;` for `&`
- **PyMuPDF4LLM** lost the headings of 6.1.16 (Complete Discharge) and 6.2.4 (Claims). Their text attached to the clause before, so a citation would name the wrong clause. Nine "Simplified for you" sidebars came out as headings in the middle of clauses
- **MarkItDown** has no headings. On pages with a sidebar, each output line holds half a line of the clause and half a line of the sidebar
- **All three** keep the page footer (product name and UIN) 34 times, at every page break, and keep "lnsured" and "ln" from the PDF's own text layer

### PyMuPDF4LLM on all 9 wordings, 2026-10-20

| Document | Pages | Same hash | Clause check against text layer | Repeated on every page |
|---|---|---|---|---|
| HDFC ERGO my:Optima Secure | 69 | yes | 35 found, 0 missing | page header, 68x |
| HDFC ERGO Medisure Super Top Up | 35 | yes | 106 found, 0 missing | page header, 35x |
| HDFC ERGO Optima Wellbeing (add-on) | 8 | yes | 3 found, 0 missing | page header, 8x |
| Niva Bupa ReAssure 2.0 | 34 | yes | 135 found, 2 missing | footer with UIN, 34x |
| Niva Bupa Health Recharge | 50 | yes | 25 found, 0 missing | footer with UIN, 50x |
| Niva Bupa Safeguard (rider) | 4 | yes | no numbered clauses | footer with UIN, 4x |
| National Parivar Mediclaim Plus | 25 | yes | 147 found, 0 missing | footer with UIN, 25x |
| National Super Top Up | 21 | yes | 144 found, 0 missing | registered office, 20x |
| National Non-Medical Expenses (add-on) | 2 | yes | no numbered clauses | none |

By insurer:

- **Niva Bupa** numbers clauses 2, 2.1, 2.1.1. Every page has a footer with the product name and UIN. ReAssure 2.0 lost two headings (above). Health Recharge put every heading at level 1, made 3.1 a list item, and turned 12 "What is covered" labels into headings
- **HDFC ERGO** uses SECTION A to E, roman numerals, and numbers that restart at 1 in each section, so a clause id is section plus number (E.4). The documents open with a printed table of contents. The page header "Policy Wording <product>" comes out as a heading on every page. Some numbers split from their titles ("6." and "Cancellation" as two headings). OCR ran on 9 pages of my:Optima Secure and 6 of 8 pages of Optima Wellbeing, whose pages are images. That is why no UIN was found in its text layer
- **National** numbers clauses 1.1 and 1.1.1 and was complete against the text layer. Parivar Plus has a footer with the UIN, Super Top Up repeats the registered office instead

## Conclusion so far

PyMuPDF4LLM lost no text in 9 documents. Every problem found is structural and can be detected: lost or demoted headings, page headers and footers, labels promoted to headings. The clean-up rules differ per insurer template, and the reference list has to follow each insurer's numbering scheme. Next: the decision as an ADR, then a clean-up step per insurer with the reference-list check.
