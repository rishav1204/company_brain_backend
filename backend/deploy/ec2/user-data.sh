#!/bin/bash
# EC2 user-data (Amazon Linux 2023): clone repo and bootstrap.
# Set GIT_REPO_URL before launching the instance, e.g. via EC2 user-data env.
set -euo pipefail

APP_DIR="/opt/company-brain"
GIT_REPO_URL="${GIT_REPO_URL:-}"

yum update -y
yum install -y git

if [[ -n "${GIT_REPO_URL}" ]]; then
  git clone "${GIT_REPO_URL}" "${APP_DIR}"
else
  mkdir -p "${APP_DIR}"
  echo "Set GIT_REPO_URL or copy the repo to ${APP_DIR} manually"
fi

if [[ -f "${APP_DIR}/backend/deploy/ec2/bootstrap.sh" ]]; then
  chmod +x "${APP_DIR}/backend/deploy/ec2/bootstrap.sh"
  bash "${APP_DIR}/backend/deploy/ec2/bootstrap.sh"
fi
