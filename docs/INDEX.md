# Docs Index

Load only what's relevant to your task.

| File | Purpose | When to read |
|---|---|---|
| [ARCHITECTURAL-GUIDELINES.md](ARCHITECTURAL-GUIDELINES.md) | Philosophy, code, testing, infra, security, shipping principles | Architecture decisions or any new pattern |
| [README.md](README.md) | Docs directory overview | Orienting in the docs folder |
| [adr/TEMPLATE.md](adr/TEMPLATE.md) | ADR template | Writing a new architecture decision record |
| [specs/TEMPLATE.md](specs/TEMPLATE.md) | Feature spec template | Writing a new feature spec |
| [runbooks/TEMPLATE.md](runbooks/TEMPLATE.md) | Runbook template | Writing a new incident runbook |
| [benchmarks/pdf-converters.md](benchmarks/pdf-converters.md) | PDF to markdown converters compared on real wordings | Touching conversion or ingestion |
| [adr/001-pdf-converter.md](adr/001-pdf-converter.md) | Why PyMuPDF4LLM converts the PDFs, and the clean-up and reference check that go with it | Touching conversion or ingestion |
| [adr/002-lambda-deploy.md](adr/002-lambda-deploy.md) | Why it runs on Lambda from a container image, and how GitHub Actions deploys it through OIDC | Touching `infra/`, the Dockerfile or the deploy workflow |
| `adr/` | Architecture decision records | Task touches a past architectural decision |
| `specs/` | Feature specs | Implementing or modifying a specific feature |
| `runbooks/` | Incident runbooks | Debugging production or modifying observability |
| `internal/` | Personal working habits (gitignored, local only) | **Always** — see CLAUDE.md |
| `archive/` | Archived docs | **NEVER** — unless explicitly asked |
