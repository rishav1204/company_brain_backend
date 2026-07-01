# EC2 production deployment (ap-south-1)

Single EC2 instance running API + worker + scheduler via Docker Compose.
Secrets load from AWS Secrets Manager at boot; S3 + Textract use the EC2 IAM instance profile.

## Layout

```
backend/deploy/ec2/
  docker-compose.prod.yml   # api, worker, scheduler
  bootstrap.sh              # install Docker, fetch secrets, start stack
  run-migrations.sh         # one-off Neon migrations
  env.prod.template         # non-secret compose overrides
  iam-policy.json           # IAM policy for EC2 instance role
  secrets-template.json     # Secrets Manager JSON shape
  provision-aws.sh          # create S3 buckets + secret scaffold (AWS CLI)
  README.md                 # this file
```

## Quick start

1. Run `provision-aws.sh` (or create resources manually — see below).
2. Put app secrets in Secrets Manager secret `company-brain/prod/app`.
3. Launch EC2 (t3.small+, Amazon Linux 2023) in `ap-south-1` with IAM role from `iam-policy.json`.
4. Copy repo to `/opt/company-brain` or configure ECR image in compose.
5. Run `sudo bash bootstrap.sh`.
6. Run `sudo bash run-migrations.sh` once before traffic.
7. Smoke test: `curl http://localhost:8000/health` and `curl http://localhost:8000/ready`.

## Secrets Manager

Secret name: `company-brain/prod/app` (JSON). See `secrets-template.json`.

Do **not** store `AWS_ACCESS_KEY_ID` when using an instance profile.

## S3 buckets

| Bucket | Env var |
|--------|---------|
| `company-brain-docs-prod` | `DOCUMENTS_S3_BUCKET` |
| `company-brain-textract-prod` | `TEXTRACT_S3_BUCKET` |

Textract staging keys: `textract-staging/{source_bucket}/{source_key}` (lifecycle: expire after 7 days).

## Production env (compose + secret)

```
APP_ENV=prod
STORAGE_PROVIDER=s3
AWS_REGION=ap-south-1
DOCUMENTS_S3_BUCKET=company-brain-docs-prod
TEXTRACT_S3_BUCKET=company-brain-textract-prod
OCR_PROVIDER=aws_textract
POSTGRES_REQUIRE_TLS=true
ENABLE_DEV_AUTH_ROUTES=false
DISABLE_DEV_AUTH_ROUTES_IN_PROD=true
OBSERVABILITY_REQUIRE_IN_PROD=false
```

## HTTPS

- **ALB + ACM** (recommended): target group → EC2:8000
- **Nginx on host**: terminate TLS → `127.0.0.1:8000`

## CI/CD

See `.github/workflows/backend-deploy-ec2.yml` for ECR build + SSM deploy.
