#!/usr/bin/env bash
# Bootstrap EC2 host: Docker, secrets from Secrets Manager, start compose stack.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/company-brain}"
SECRET_ID="${SECRET_ID:-company-brain/prod/app}"
COMPOSE_FILE="${APP_DIR}/backend/deploy/ec2/docker-compose.prod.yml"
AWS_REGION="${AWS_REGION:-ap-south-1}"

echo "==> Installing Docker (Amazon Linux 2023 / yum)"
if ! command -v docker &>/dev/null; then
  sudo yum update -y
  sudo yum install -y docker jq
  sudo systemctl enable docker
  sudo systemctl start docker
  sudo usermod -aG docker "${USER}" || true
fi

if ! docker compose version &>/dev/null; then
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

echo "==> Preparing ${APP_DIR}"
sudo mkdir -p "${APP_DIR}"
sudo chown -R "${USER}:${USER}" "${APP_DIR}" || true

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "ERROR: ${COMPOSE_FILE} not found. Clone the repo to ${APP_DIR} first."
  exit 1
fi

echo "==> Fetching secrets from ${SECRET_ID}"
SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_ID}" \
  --region "${AWS_REGION}" \
  --query SecretString \
  --output text)"

echo "${SECRET_JSON}" | jq -r 'to_entries | map("\(.key)=\(.value|tostring)") | .[]' > "${APP_DIR}/.env"
chmod 600 "${APP_DIR}/.env"

echo "==> Building and starting containers"
cd "${APP_DIR}/backend/deploy/ec2"
export DOCUMENTS_S3_BUCKET="${DOCUMENTS_S3_BUCKET:-company-brain-docs-prod}"
export TEXTRACT_S3_BUCKET="${TEXTRACT_S3_BUCKET:-company-brain-textract-prod}"
docker compose -f docker-compose.prod.yml up -d --build

echo "==> Done. API health: curl http://localhost:8000/health"
