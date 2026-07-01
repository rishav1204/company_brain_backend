#!/usr/bin/env bash
# Provision AWS resources for EC2 deployment (ap-south-1).
# Requires: AWS CLI configured with permissions to create S3, IAM, Secrets Manager.
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
DOCS_BUCKET="${DOCS_BUCKET:-company-brain-docs-prod}"
TEXTRACT_BUCKET="${TEXTRACT_BUCKET:-company-brain-textract-prod}"
SECRET_NAME="${SECRET_NAME:-company-brain/prod/app}"
IAM_ROLE_NAME="${IAM_ROLE_NAME:-company-brain-ec2-role}"
INSTANCE_PROFILE_NAME="${INSTANCE_PROFILE_NAME:-company-brain-ec2-profile}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Region: ${AWS_REGION}"

create_bucket() {
  local bucket="$1"
  if aws s3api head-bucket --bucket "${bucket}" 2>/dev/null; then
    echo "Bucket ${bucket} already exists"
    return
  fi
  echo "Creating bucket ${bucket}"
  if [[ "${AWS_REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${bucket}" --region "${AWS_REGION}"
  else
    aws s3api create-bucket \
      --bucket "${bucket}" \
      --region "${AWS_REGION}" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}"
  fi
  aws s3api put-public-access-block \
    --bucket "${bucket}" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
}

create_bucket "${DOCS_BUCKET}"
create_bucket "${TEXTRACT_BUCKET}"

echo "==> Textract bucket lifecycle (expire textract-staging/ after 7 days)"
aws s3api put-bucket-lifecycle-configuration \
  --bucket "${TEXTRACT_BUCKET}" \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "expire-textract-staging",
      "Status": "Enabled",
      "Filter": { "Prefix": "textract-staging/" },
      "Expiration": { "Days": 7 }
    }]
  }' 2>/dev/null || echo "Lifecycle rule may already exist or requires bucket versioning off"

echo "==> IAM role ${IAM_ROLE_NAME}"
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "ec2.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}'
aws iam create-role \
  --role-name "${IAM_ROLE_NAME}" \
  --assume-role-policy-document "${TRUST_POLICY}" 2>/dev/null || echo "Role may already exist"

aws iam put-role-policy \
  --role-name "${IAM_ROLE_NAME}" \
  --policy-name "company-brain-ec2-policy" \
  --policy-document "file://${SCRIPT_DIR}/iam-policy.json"

aws iam create-instance-profile \
  --instance-profile-name "${INSTANCE_PROFILE_NAME}" 2>/dev/null || echo "Instance profile may already exist"

aws iam add-role-to-instance-profile \
  --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
  --role-name "${IAM_ROLE_NAME}" 2>/dev/null || true

echo "==> Secrets Manager secret ${SECRET_NAME}"
if ! aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${AWS_REGION}" &>/dev/null; then
  aws secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --region "${AWS_REGION}" \
    --secret-string "file://${SCRIPT_DIR}/secrets-template.json"
  echo "Created secret — update values in AWS Console or:"
  echo "  aws secretsmanager put-secret-value --secret-id ${SECRET_NAME} --secret-string file://your-secrets.json"
else
  echo "Secret already exists"
fi

cat <<EOF

==> Provisioned:
  S3 documents:  ${DOCS_BUCKET}
  S3 textract:   ${TEXTRACT_BUCKET}
  IAM role:      ${IAM_ROLE_NAME}
  Instance prof: ${INSTANCE_PROFILE_NAME}
  Secret:        ${SECRET_NAME}

Next steps:
  1. Update secret values in Secrets Manager
  2. Launch EC2 t3.small+ in ${AWS_REGION} with instance profile ${INSTANCE_PROFILE_NAME}
  3. Clone repo to /opt/company-brain and run bootstrap.sh
  4. Run run-migrations.sh once

EOF
