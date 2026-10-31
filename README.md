# Fargate App Hub

Fargate App Hub is an Amazon ECS Fargate platform, not Kubernetes. A shared application load balancer routes application domains to independently managed services. Each application retains both standalone installation and Fargate App Hub installation through its own full and existing-infrastructure CloudFormation templates.

## Usage

Copy `.env.example` to `.env`, select your AWS profile, region, and platform stack. `bash apphub.sh status` inspects the platform; `outputs` prints attachment values; `catalog` lists applications; `validate` checks the infrastructure template. Run `npm test` for configuration checks.

Use `bash open-fargate.sh plan CREATE open-fargate-create path/to/private.parameters.json` to prepare a platform in an existing VPC using PublicSubnets and an issued CertificateArn. Review with `bash open-fargate.sh review open-fargate-create`, then execute only after review with `bash open-fargate.sh execute open-fargate-create --reviewed`. For an existing platform use UPDATE and its exact stack name. No app is automatically installed. Filled parameters and credentials must remain ignored.

## Independent application deployments

Use each app's full template for standalone installation or existing template to attach to Fargate App Hub using Cluster, ListenerArn, LoadBalancerSecurityGroup, VpcId and private service subnets. Each app needs its own host rules, target groups, domain certificate, and data resources. Optional DNS changes must not replace existing records without a reviewed cutover. The shared HTTP listener redirects to HTTPS; its default HTTPS response is 404 for unregistered hosts.

Four applications are identified: OpenADA, GuardScale, AutoVision, and SmartDetector. Osirus stays separate. The fifth application is pending identification.

## Migration safety

Migrate current stacks in place with existing credentials and data; do not delete a stack and recreate its database. Stage retention protection for old networking before the migration change set. Inspect changes for database, bucket, queue, Redis, or secret modifications before execution. Verify ECS services, healthy ALB targets, HTTPS with the intended hostname, and login before switching DNS. Only remove old ALBs after DNS propagation and verified traffic on Fargate App Hub.

The running infrastructure currently uses stack name `shared-apps-platform`; CloudFormation stacks cannot be renamed in place. New installations can use `apphub-platform`. Fargate App Hub is the display/platform name for both.

## Deployment permissions

AutoVision and SmartDetector deployments encountered missing EventBridge and Route 53 read permissions. `devops/iam/apphub-app-deployment-additions.json` is a policy supplement for an administrator to review and scope; this project does not grant permissions itself. Restore deletion permissions before cleaning up failed stack resources.

The current installs use `EventBridgeEnabled=false` and direct SQS incident delivery. The standalone and existing-infrastructure app templates default to EventBridge enabled. DNS aliases were applied separately because the deployment identity cannot read hosted-zone metadata through CloudFormation.

## Deployment verification

The four identified apps run in the shared cluster. HTTPS health checks, AutoVision and SmartDetector root login, AutoVision API-key detection, SmartDetector's AutoVision integration, and a simulated incident processed by the SQS worker were verified. OpenADA's www hostname redirects to its apex domain. The previous OpenADA and GuardScale ALBs and empty clusters were removed; application databases, buckets, queues, and credentials were preserved.

The two earlier failed AutoVision/SmartDetector stacks have been removed. Root credentials remain only in ignored local parameter files; never commit or print them in status output.

## CloudFormation-only lifecycle

Install, update, and delete apps through formal CloudFormation templates and reviewed change sets. Do not delete individual infrastructure resources manually. Import verified unused orphaned resources before CloudFormation-managed cleanup, then remove the temporary cleanup stack.

GuardScale and OpenADA now use `guardscale-apphub` and `openada-apphub`. Their former test stacks and the temporary cleanup stack have been deleted through CloudFormation. Preserved storage was imported into the new app stacks, with original physical resource identifiers verified. See [RECOVERY.md](RECOVERY.md) for the reusable recovery workflow, private configuration exporter, and optional scheduled-backup template. Scheduled data backups are not enabled by saving the workflow.

## Cloud hosting integration

Fargate App Hub is the public product name; existing `apphub` filenames, environment aliases, tags, and physical identifiers are preserved for compatibility. `open-fargate.sh` is the preferred entry point.

`contract` prints the versioned hosting contract. `attachment` reads CloudFormation outputs and emits the engine and attachment identifiers. Update older platform stacks through a reviewed change set to add missing outputs. Private service subnets and application-specific certificates remain explicit inputs; public ALB subnets must not be substituted for service subnets automatically.

Cloud must implement a Fargate adapter for the existing Cluster entity and lifecycle actions before this can be sold as shared hosting. Do not run Kubernetes namespace or Helm operations against this engine. Seller ownership, buyer subscription, capacity enforcement, task-role boundaries, host-rule allocation, and organization-scoped status/log access must be resolved server-side. Buyers must not receive platform owner credentials or unrestricted cluster access.

CMS Serverless is the first intended application. Its existing-infrastructure template must reuse these outputs, allocate independent task roles, security groups and storage, and support explicit SQL and MongoDB connections. A shared RDS server alone does not satisfy CMS's MongoDB requirement. Reusing databases needs per-installation databases/users, secret references, backups, and deletion ownership; this platform does not yet provision or share a database. No claim of CMS launch readiness is made until that application template and Cloud adapter are tested together.

No release bucket URL or `cloud.yaml` import is fabricated here. The Cloud catalog buildspec should be connected once the Fargate adapter and real versioned artifact destination exist.

## Repository

Canonical source: https://github.com/techcto/fargate. Cloud checks this repository out at `submodules/fargate`. The earlier local AppHub checkout is preserved; new development belongs here.
