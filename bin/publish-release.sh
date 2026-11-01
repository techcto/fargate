#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
release_version="${1:?Supply the semantic release version without v}"
[[ "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo 'Use a semantic version such as 0.1.0.' >&2
  exit 1
}
release_bucket="${FARGATE_RELEASE_BUCKET:-fargate-aws}"
release_region="${AWS_REGION:-us-east-1}"
release_prefix="s3://${release_bucket}/cloudformation/fargate/${release_version}"
# Match Kubernetes publication: no catalog writes and no application deployment.
# GitFlow imports the tagged cloud.yaml after artifact publication succeeds.
for template in apphub.yaml cms-existing.yaml; do
  aws s3 cp "devops/cloudformation/${template}" "${release_prefix}/${template}" \
    --content-type text/yaml --region "$release_region" --no-progress
done
aws s3 cp configs/hosting-contract.json "${release_prefix}/hosting-contract.json" \
  --content-type application/json --region "$release_region" --no-progress
