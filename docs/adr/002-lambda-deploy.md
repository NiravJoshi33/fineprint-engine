# 002 Run on Lambda from a container image, deployed by GitHub Actions

**Status:** Accepted
**Date:** 2026-11-15

## Context

The engine needs a cloud deploy that costs nothing while idle, because most days nobody calls it.

The image is big. CPU-only torch plus the two models (bge-small-en-v1.5 for vectors, bge-reranker-base for re-ranking) come to about 1.7 GB, and Lambda's filesystem is read-only, so the models have to ship inside the image. The image also needs the policy text, and that can't go in git: the repo is public and the insurers' redistribution terms aren't checked.

Generation runs outside AWS, through the gateway in `gateway.py`: Azure Foundry first, then OpenCode Go, then OpenRouter. Bedrock was the plan, but the new account had zero Bedrock quotas, so it's out for now.

## Decision

The API runs as a Lambda function from a container image (arm64, 3,008 MB, 300 s timeout) behind a function URL with `AWS_IAM` auth, in eu-north-1. Terraform (`infra/`) creates everything. GitHub Actions (`.github/workflows/deploy.yml`) deploys every push to `main` that changes what goes into the image.

- CI signs in through OIDC. The role trusts only this repo's `main`, in GitHub's immutable subject format (`repo:OWNER@ID/REPO@ID:...`), and can only push to one ECR repo, update one function and read one S3 object
- The policy text sits in a private S3 bucket. Terraform uploads it from my machine, CI copies it in before the build
- Terraform sets the first image and then ignores it (`ignore_changes = [image_uri]`). The workflow owns the image after that
- ECR keeps the last 3 images

## Consequences

- **Easier:** idle costs nothing. The 12 calls up to the morning of 15 Nov used about 2,970 GB-s and billed $0. A deploy is a push, and the first CI run took 4 min 47 s, ending with the new image live. No AWS key is stored in GitHub
- **Easier:** rollback is one command, `aws lambda update-function-code --image-uri` with an earlier tag, because ECR still holds the last 3
- **Harder:** cold starts. A new account is capped at 3,008 MB (2 vCPUs). The first request took about 90 s on 14 Nov, mostly embedding the corpus at startup (24 s) and re-ranking 43 chunks (42 s), and 158 s right after a new image went live on 15 Nov. The same work takes about 2 s on an M-series Mac
- **Harder:** the runner starts empty every time, so every deploy installs torch and downloads both models again, even for a one-line code change
- **Harder:** two tools touch the function. Changing the image in `main.tf` now does nothing. Everything else still goes through `terraform apply` from my machine, where the state lives
- **Harder:** CI has no smoke test. A green run means Lambda accepted the image, not that the answers are right. For now the check is a signed curl from my machine
- **Cost per question:** Lambda's share is $0 so far, inside the free monthly allowance. The LLM's share isn't measured yet
- **Revisit if:** cold starts stay over a minute after the embedding and re-ranker fixes, the account's memory cap is lifted (more memory on Lambda means more vCPUs), Bedrock quotas open, or the insurers' terms allow the policy text in git

## Alternatives considered

- **App Runner:** the fallback if cold starts were too slow. It isn't offered in eu-north-1, and it keeps an instance provisioned, which bills while idle
- **Lambda from a zip:** the limit is 250 MB unzipped. Torch and the two models are far over it
- **ECS or EC2:** bill while idle, and EC2 is a server to patch
- **An AWS access key in GitHub secrets:** works until it leaks, then works for whoever has it, from anywhere, until someone rotates it. OIDC credentials expire in about an hour and only `main` can get them
- **Policy text in git:** a takedown notice could disable the repo, and every new insurer would need its terms checked before its documents could be added
