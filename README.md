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

## CMS Serverless

CMS Serverless is a separate catalog product maintained in `solodev-dcx/cms`.
Its versioned `solodev-cms-serverless.yaml` template owns each application's
service, DNS, isolated databases, session namespace and EFS access point.
AppHub publishes only the shared platform and allocator code. See
[CMS-INTEGRATION.md](CMS-INTEGRATION.md) for the attachment contract.

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

App installers create and upgrade tables in their own database. Allocation rollback/delete never drops data. Created database and writer resources belong to this platform stack and are deleted by an explicitly approved product deletion. Existing-mode databases remain owned by their original stack. Back up and migrate customer data before approving any destructive deletion or replacement.

The provider source is `functions/tenant-database/index.py`; its deployed inline copy in `apphub.yaml` must match. Local verification: `python3 tests/tenant_database_test.py`. No new pipeline test stage is required.

These templates are prepared for native Cloud integration. They do not by themselves enable metered billing or complete CMS storage/MongoDB provisioning; keep the listing draft until the full launch is verified.

## Optional shared data services and backup ownership

`DocumentDbMode`, `FileSystemMode`, and `RedisMode` each accept None/Create/Existing, defaulting to None. New services use private subnets and dedicated security groups. Application stacks add only their own ingress rules. EFS requires encrypted transport and app-owned access points. DocumentDB and shared Valkey must use tenant-scoped credentials; endpoints alone do not grant access. The Valkey cache attaches an initially empty VALKEY user group. AWS disables its default user automatically; no dummy default-user password or secret is needed. Tenant password/IAM users must be provisioned before applications can connect. See [AWS Valkey RBAC](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Clusters.RBAC.html).

When `EnableBackups=true`, the selected Aurora, DocumentDB and EFS resources are explicitly enrolled in a daily AWS Backup plan and stack-owned vault. `BackupRetentionDays` defaults to 30. Redis/Valkey uses native daily snapshots with seven-day retention; it is not represented as AWS Backup coverage. Network/compute resources are not data backups. The platform owns and deletes each created data service and its supporting security, subnet and user groups together; existing-mode services are external references and are never deleted by this stack.

Whole-cluster recovery points belong to the hosting organization. A consuming organization's restore must not replace other tenants' data. Tenant restores require restoring to an isolated recovery target and importing only the selected tenant, followed by application-level verification.

## Private and shared commercial offers

Fargate App Hub is the private-stack product: the purchasing organization owns the AWS bill and pays the approved $5/vCPU-month management rate, prorated by runtime. SpaceMade Shared Fargate is a distinct hosted listing backed by a SpaceMade-owned stack. Hosting subscriptions allocate customer capacity without exposing the host's credentials or root data-service secrets.

Shared hosting needs separate usage and allowance units for compute runtime, SQL, DocumentDB, cache, filesystem storage and backup retention/storage. Do not bill an entire shared DB or ALB again for every application. Additional service rates have not been approved. Database endpoints and EFS access points do not themselves provide tenant usage measurement or filesystem hard quotas; do not claim either before the relevant meter and enforcement are implemented and tested.

Existing Redis/cache attachments keep the external owner's snapshot policy; their backup coverage must be verified before displaying them as protected. AWS Backup coverage reference: https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html

## Secret inputs

Cloud uses the existing buildspec `${Generator.MediumPassword.48}` for `DocumentDbAdminPassword`. Direct CloudFormation installations supply the same NoEcho parameter. The template stores it in the stack-owned DocumentDB administrator secret; it never returns the password as an output. Updates retain the existing parameter unless password rotation is explicitly requested. Passwords are not embedded in release artifacts, generated by custom Lambda code, or regenerated during upgrades. Aurora continues to use its native RDS-managed master secret. Valkey has no dummy default-user secret.

## Official install and upgrade artifact

The cluster product has one canonical CloudFormation installer: `devops/cloudformation/apphub.yaml`. Tagged releases publish it at `cloudformation/fargate/VERSION/apphub.yaml`, and `cloud.yaml` references that same artifact. New installations use a reviewed CREATE change set; upgrades use a reviewed UPDATE change set against the same stack. Optional data services remain normal parameters in that template. Application templates install applications into the platform; they are not alternate cluster installers.

## Product deletion

The official template uses Delete for stack-owned resources, including replacement policies; it does not silently detach retained AWS resources. Database deletion protection is disabled in this new-product template so an approved CloudFormation product deletion can finish. Existing-mode services are never created or deleted by this stack. Treat product deletion and data-resource replacement as destructive operations requiring backup/migration review.

AWS Backup refuses to delete a vault that still contains recovery points. Resolve the backup retention choice before deleting the platform: preserve required backups in an explicitly managed external vault or explicitly remove them through Backup Manager. Cloud must keep the stack/resource record until CloudFormation confirms DELETE_COMPLETE; a failed or blocked deletion is not a successful removal. No automatic backup-purge Lambda or alternate installer is added.
