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

## CMS attachment template

`devops/cloudformation/cms-existing.yaml` is a candidate existing-infrastructure CMS application stack. AWS CloudFormation template validation passes; no install has been executed. It requires immutable CMS/UI image digests, private service subnets with egress to image registries and AWS APIs, an existing encrypted EFS filesystem, and pre-provisioned tenant-specific SQL credentials, Mongo endpoint, Redis endpoint, and SSO client.

The existing Secrets Manager secret must contain `db_user`, `db_password`, `app_secret`, `admin_user`, `admin_password`, and `sso_client_secret`. Use the default Secrets Manager encryption key; a customer-managed KMS key requires a separately reviewed, scoped decrypt policy. Do not supply a server master login. The current CMS Mongo database is fixed to `solodev_views`, so Mongo must be isolated per tenant until CMS supports configurable database names. Redis likewise requires an isolated endpoint.

The platform owner reserves an unused listener priority and installs the hostname's certificate on the shared HTTPS listener before launch. DNS and additional site/alias host rules are not created by this candidate template. Cloud must manage those lifecycle steps before offering self-service CMS hosting. Desired count is one; updates briefly stop the old task to prevent simultaneous initialization against the same tenant data. This is the lower-cost single-instance option, not high availability.

The template creates application IAM roles scoped to its tenant secret, logs and EFS access point. It retains the access point and logs on deletion, and never owns the shared database servers, filesystem, cluster or load balancer. Review the full change set before running it. `cloud.yaml` describes the platform release only; it does not register or publish a CMS product automatically.

Prepare an application change set against the existing platform:

```sh
bash open-fargate.sh plan-app CREATE cms-test cms-test-create devops/cloudformation/cms-existing.yaml path/to/private.parameters.json
bash open-fargate.sh review-app cms-test cms-test-create
# After reviewing IAM, data retention and availability impact:
bash open-fargate.sh execute-app cms-test cms-test-create --reviewed
```

Use UPDATE for an existing application stack. The private parameters file is a standard CloudFormation parameter array. Omit Cluster, ListenerArn, LoadBalancerSecurityGroup and VpcId: the command resolves those from the backing stack and rejects overrides. Preparing a change set does not execute it. Do not pass raw credentials in parameters; use the tenant secret ARN. These commands operate only in the configured AWS profile/account and do not change Cloud catalog or billing records.

## Kubernetes-compatible release flow

This repository follows `techcto/aws-kubernetes`: a `vMAJOR.MINOR.PATCH` GitHub tag publishes versioned CloudFormation templates to S3; Cloud's connected Git provider imports `cloud.yaml`. GitHub Actions does not write catalog records or deploy application infrastructure.

Use the same existing publisher-account configuration as Kubernetes: repository/organization variable `MP_AWS_ACCESS_KEY_ID`, secured secret `MP_AWS_SECRET_ACCESS_KEY`, and optional `AWS_REGION`. These are variable names only; no keys are stored in this repository. The existing S3 publisher needs write access to `s3://fargate-aws/cloudformation/fargate/*`. If organizational secrets/variables are repository-restricted, grant this repository access to the existing configuration. GitHub does not automatically inherit another repository's private secrets.

The default release bucket is the `fargate-aws` bucket with a separate `cloudformation/fargate/VERSION` prefix. No bucket, policy, or IAM role is created by this workflow. Overriding the bucket requires updating `cloud.yaml` to the matching real artifact URL before tagging. Artifact accessibility must match the Kubernetes templates so CloudFormation can read them.

In Cloud, bind the Fargate App Hub Cluster item to the same SpaceMade Git provider used by Kubernetes, with repository `techcto/fargate`. Select SpaceMade's existing AWS provider at launch. Seller release publication and customer infrastructure deployment remain separate account roles. Draft imports remain draft until the Fargate runtime/tenant capacity gates are complete.

## SpaceMade GitFlow connection

SpaceMade's `fargate-app-hub` Cluster catalog item links to `techcto/fargate` through the same connected GitHub provider as `techcto/aws-kubernetes`. The GitHub repository owner is `techcto`; the selling Cloud organization is SpaceMade. Branch pushes exercise webhook delivery without creating catalog versions. Semantic release tags import draft versions through GitFlow after release artifacts are available.

Private management terms: SpaceMade charges $5 per provisioned vCPU-month, prorated by running time. The cluster owner pays AWS infrastructure directly and sets its own application resale prices. These commercial terms are approved; paid activation remains gated on verified metering and lifecycle tests.

### Release artifact access

Cloud's existing catalog fetcher downloads templates over public HTTPS. The first release uploaded successfully, but anonymous reads returned HTTP 403. `devops/policy/public-release-read.statement.json` is a single proposed statement to merge into the bucket's existing CloudFormation-managed policy after reviewing ownership and current statements. It is not a replacement bucket policy or an executable deployment template. Preserve all unrelated statements and keep non-release prefixes private. S3 account/bucket public-access settings must permit this specific bucket-policy grant; the statement alone cannot override a public-access block. Do not change application buckets, data, credentials, or other prefixes to resolve release access.

## Optional shared platform services

`LoadBalancerMode` accepts `Create` (default), `Existing`, or `None`. Existing mode binds an HTTPS listener and its security group without taking ownership of the load balancer. Compute-only clusters omit the HTTP outputs. HTTP applications must require the listener capability before launch.

`DatabaseMode` accepts `None` (default), `Create`, or `Existing`. Create provisions **one shared Aurora MySQL Serverless v2 cluster**, with a private writer, encryption, seven-day backup retention, a Secrets Manager-managed administrator password, and Data API enabled. It requires private subnets in at least two Availability Zones. Min/max ACU default to 0.5/2; AWS database charges are separate from Fargate management. Existing mode requires an Aurora MySQL Data API cluster, its endpoint, security group and administrator secret. Generic RDS MySQL without Data API requires a different provisioning adapter and is not silently treated as compatible.

The platform exports `TenantDatabaseProviderArn`. Application CloudFormation stacks allocate their database through `Custom::AppHubDatabase`, with `ServiceToken` set to that output and `TenantSecretArn` pointing to an app-owned secret. The secret name must be under `/spacemade/fargate/PLATFORM_STACK_NAME/tenants/` and carry `PlatformStackId` and `ApplicationStackId` tags matching the actual stack identities. Generate its `db_password` as 32–64 alphanumeric characters. The provider derives the database/user identities from the application stack ID, grants access only to that database, and writes `db_user`/`db_database` into the tenant secret. Apps receive their secret; they never receive the platform administrator secret.

App installers create and upgrade tables in their own database. Allocation rollback/delete never drops data. Shared database and writer resources have Retain policies and deletion protection; deleting the compute platform must not delete customer databases. A separate reviewed data-retention/migration flow is needed before permanently removing retained database resources.

The provider source is `functions/tenant-database/index.py`; its deployed inline copy in `apphub.yaml` must match. Local verification: `python3 tests/tenant_database_test.py`. No new pipeline test stage is required.

These templates are prepared for native Cloud integration. They do not by themselves enable metered billing or complete CMS storage/MongoDB provisioning; keep the listing draft until the full launch is verified.

## Optional shared data services and backup ownership

`DocumentDbMode`, `FileSystemMode`, and `RedisMode` each accept None/Create/Existing, defaulting to None. New services use private subnets and dedicated security groups. Application stacks add only their own ingress rules. EFS requires encrypted transport and app-owned access points. DocumentDB and shared Valkey must use tenant-scoped credentials; endpoints alone do not grant access. The new Valkey cache starts with its default user disabled, so it remains inaccessible until the tenant ACL membership provisioner is complete.

When `EnableBackups=true`, the selected Aurora, DocumentDB and EFS resources are explicitly enrolled in a daily AWS Backup plan and retained vault. `BackupRetentionDays` defaults to 30. Redis/Valkey uses native daily snapshots with seven-day retention; it is not represented as AWS Backup coverage. Network/compute resources are not data backups. Retained databases/cache also retain their required security groups and subnet/user groups so deleting a platform does not leave a retained database referencing resources CloudFormation is trying to remove.

Whole-cluster recovery points belong to the hosting organization. A consuming organization's restore must not replace other tenants' data. Tenant restores require restoring to an isolated recovery target and importing only the selected tenant, followed by application-level verification.

## Private and shared commercial offers

Fargate App Hub is the private-stack product: the purchasing organization owns the AWS bill and pays the approved $5/vCPU-month management rate, prorated by runtime. SpaceMade Shared Fargate is a distinct hosted listing backed by a SpaceMade-owned stack. Hosting subscriptions allocate customer capacity without exposing the host's credentials or root data-service secrets.

Shared hosting needs separate usage and allowance units for compute runtime, SQL, DocumentDB, cache, filesystem storage and backup retention/storage. Do not bill an entire shared DB or ALB again for every application. Additional service rates have not been approved. Database endpoints and EFS access points do not themselves provide tenant usage measurement or filesystem hard quotas; do not claim either before the relevant meter and enforcement are implemented and tested.

Existing Redis/cache attachments keep the external owner's snapshot policy; their backup coverage must be verified before displaying them as protected. AWS Backup coverage reference: https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html
