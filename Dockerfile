# REF: https://docs.astral.sh/uv/guides/integration/aws-lambda/#deploying-a-docker-image
# Build for Lambda arm64: docker build --platform linux/arm64 -t fineprint .

# Stage 1: only lends the uv binary to the builder (RUN --mount=from=uv)
FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

# Stage 2: installs the dependencies into the Lambda task root
FROM public.ecr.aws/lambda/python:3.12 AS builder

# Enable bytecode compilation, to improve cold-start performance.
ENV UV_COMPILE_BYTECODE=1

# Disable installer metadata, to create a deterministic layer.
ENV UV_NO_INSTALLER_METADATA=1

# Enable copy mode to support bind mount caching.
ENV UV_LINK_MODE=copy

# Use the base image's Python, never download one; install into a throwaway venv
ENV UV_PYTHON=python3.12 UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv

# `uv sync --frozen` installs exactly what uv.lock records, including where each wheel comes
# from. The guide's `uv export` + `uv pip install` loses that: the exported list says
# torch==2.14.1+cpu but not that it lives on the PyTorch CPU index, so the install fails.
# --no-install-project: only dependencies here; the code is copied in the last stage, so this
# layer stays cached across code changes as long as uv.lock and pyproject.toml are unchanged.
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project --no-editable

# Stage 3: downloads the two models the pipeline loads, through the same loaders the code uses,
# so only the files they read come down. Names must match vectors.py and rerank.py: with
# HF_HUB_OFFLINE=1 a mismatch fails at cold start instead of silently downloading.
FROM builder AS models
ENV HF_HOME=/opt/hf
RUN /opt/venv/bin/python -c "\
from sentence_transformers import CrossEncoder, SentenceTransformer; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); \
CrossEncoder('BAAI/bge-reranker-base')"

# Stage 4, the image that ships: a clean base plus the installed packages, the models, the code
# and the policy text. Ordered from least to most often changed: Docker rebuilds (and ECR
# re-uploads) every layer after the first changed one, so a code change moves KBs, not GBs.
FROM public.ecr.aws/lambda/python:3.12

# the venv's packages go straight into /var/task, which is on Lambda's import path
COPY --from=builder /opt/venv/lib/python3.12/site-packages ${LAMBDA_TASK_ROOT}

# Lambda's filesystem is read-only except /tmp, so the models ship in the image; offline mode
# stops the libraries from calling Hugging Face at cold start. TQDM_DISABLE keeps bm25s
# progress bars out of the CloudWatch logs.
COPY --from=models /opt/hf /opt/hf
ENV HF_HOME=/opt/hf HF_HUB_OFFLINE=1 TQDM_DISABLE=1

# The package folder itself, so `import fineprint` resolves from /var/task
COPY ./src/fineprint ${LAMBDA_TASK_ROOT}/fineprint
COPY ./data/niva_reassure2.md ${LAMBDA_TASK_ROOT}/data/niva_reassure2.md

# module.function; Lambda splits at the last dot
CMD ["fineprint.handler.handler"]
