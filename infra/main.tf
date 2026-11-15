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
        Effect   = "Allow"
        Action   = "lambda:UpdateFunctionCode"
        Resource = aws_lambda_function.fineprint.arn
      },
    ]
  })
}

