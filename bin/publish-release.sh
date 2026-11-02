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
package_dir=$(mktemp -d)
trap 'rm -rf "$package_dir"' EXIT
python3 -m pip install --quiet --only-binary=:all: --platform manylinux2014_x86_64 \
  --implementation cp --python-version 3.13 \
  -r functions/tenant-services/requirements.txt --target "$package_dir/tenant-services"
cp functions/tenant-services/index.py "$package_dir/tenant-services/index.py"
curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o "$package_dir/tenant-services/global-bundle.pem"
(cd "$package_dir/tenant-services" && zip -qr "$package_dir/tenant-services.zip" .)
aws s3 cp "$package_dir/tenant-services.zip" "${release_prefix}/tenant-services.zip" --region "$release_region" --no-progress
python3 - "$release_version" "$package_dir/apphub.yaml" <<'PY'
import json, sys
with open('devops/cloudformation/apphub.yaml') as source:
    template = json.load(source)
template['Parameters']['ArtifactVersion']['Default'] = sys.argv[1]
with open(sys.argv[2], 'w') as destination:
    json.dump(template, destination, indent=2)
PY
# Match Kubernetes publication: no catalog writes and no application deployment.
# GitFlow imports the tagged cloud.yaml after artifact publication succeeds.
for template in apphub.yaml cms-existing.yaml; do
  template_source="devops/cloudformation/${template}"
  if [ "$template" = apphub.yaml ]; then template_source="$package_dir/apphub.yaml"; fi
  aws s3 cp "$template_source" "${release_prefix}/${template}" \
    --content-type text/yaml --region "$release_region" --no-progress
done
aws s3 cp configs/hosting-contract.json "${release_prefix}/hosting-contract.json" \
  --content-type application/json --region "$release_region" --no-progress
