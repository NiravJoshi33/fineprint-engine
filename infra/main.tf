provider "aws" {
  region  = "eu-north-1"
  profile = "NiravJ"
}

resource "aws_ecr_repository" "fineprint" {
  name                 = "fineprint"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Each image is ~1.7 GB and CI pushes one per deploy, so storage would grow with every merge.
# Three keeps the live image plus two to roll back to.
resource "aws_ecr_lifecycle_policy" "fineprint" {
  repository = aws_ecr_repository.fineprint.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 3 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      },
    ]
  })
}

resource "aws_iam_role" "fineprint_lambda" {
  name = "fineprint_lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_role_attach" {
  role       = aws_iam_role.fineprint_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "fineprint" {
  function_name = "fineprint"
  role          = aws_iam_role.fineprint_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.fineprint.repository_url}:87f7789"
  architectures = ["arm64"]
  memory_size   = 3008
  timeout       = 300

  environment {
    variables = {
      OPENROUTER_API_KEY  = var.openrouter_api_key
      OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1"
      OPENROUTER_MODEL    = "openai/gpt-oss-120b"
      OPENCODE_API_KEY    = var.opencode_api_key
      OPENCODE_ENDPOINT   = "https://opencode.ai/inference/go/openai/v1"
      OPENCODE_MODEL      = "deepseek-v4.1-flash"
      FOUNDRY_API_KEY     = var.foundry_api_key
      FOUNDRY_ENDPOINT    = "https://fineprint-ai-agent-resource.openai.azure.com/openai/v1/"
      FOUNDRY_MODEL       = "gpt-5-mini"
    }
  }

  # Terraform sets the first image; after that .github/workflows/deploy.yml owns it.
  # Without this, every apply would roll Lambda back to the tag above.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_function_url" "fineprint_url" {
  function_name      = aws_lambda_function.fineprint.function_name
  authorization_type = "AWS_IAM"
}

resource "aws_iam_openid_connect_provider" "fineprint_github" {
  url = "https://token.actions.githubusercontent.com"
  client_id_list = [
    "sts.amazonaws.com"
  ]
}

resource "aws_iam_role" "fineprint_gh_deploy" {
  name = "fineprint_gh_deploy"
  assume_role_policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [
      {
        "Effect" = "Allow",
        "Principal" = {
          "Federated" = aws_iam_openid_connect_provider.fineprint_github.arn
        },
        "Action" = "sts:AssumeRoleWithWebIdentity",
        "Condition" = {
          "StringEquals" = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:NiravJoshi33@33543795/fineprint-engine@1426559210:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "fineprint_gh_policy" {
  name = "fineprint_gh_policy"
  role = aws_iam_role.fineprint_gh_deploy.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:CompleteLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:InitiateLayerUpload",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:BatchGetImage",
        ]
        Resource = aws_ecr_repository.fineprint.arn
      },
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        # GetFunctionConfiguration is what `aws lambda wait function-updated` polls
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunctionConfiguration",
        ]
        Resource = aws_lambda_function.fineprint.arn
      },
      {
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.fineprint_data.arn}/${aws_s3_object.policy_text.key}"
      },
    ]
  })
}

data "aws_caller_identity" "current" {}

# The policy text the image bakes in. data/ is gitignored (insurer wording, redistribution
# terms unchecked), so CI's checkout doesn't have it; the deploy job fetches it from here.
resource "aws_s3_bucket" "fineprint_data" {
  bucket = "fineprint-data-${data.aws_caller_identity.current.account_id}"
}

# New buckets block public access by default; stating it means an account-level change can't open this one
resource "aws_s3_bucket_public_access_block" "fineprint_data" {
  bucket                  = aws_s3_bucket.fineprint_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Uploaded from this machine by `terraform apply`; source_hash re-uploads it when the file changes
resource "aws_s3_object" "policy_text" {
  bucket      = aws_s3_bucket.fineprint_data.id
  key         = "niva_reassure2.md"
  source      = "${path.module}/../data/niva_reassure2.md"
  source_hash = filemd5("${path.module}/../data/niva_reassure2.md")
}

