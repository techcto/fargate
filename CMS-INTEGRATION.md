# Solodev Serverless integration review

Reviewed the existing CMS source templates at `devops/cloudformation/serverless/deploy.yaml`, `serverless/cms.yaml`, and `infrastructure/fargate.yaml`.

The application is already ECS Fargate, using a PHP-FPM CMS image and Apache UI image. This is the appropriate starting point for Fargate App Hub; it does not require turning an ECS cluster into EKS. EKS on Fargate remains Kubernetes and is a separate compute choice, not an ECS deployment target.

The standalone wrapper creates ALB, ECS cluster, RDS, DocumentDB, EFS, optional Redis and Backup stacks. Preserve that standalone path. Add an existing-infrastructure target to the same versioned CMS product so it can attach to shared infrastructure.

## Changes needed before shared launch

- Consume the platform's HTTPS ListenerArn; create only a hostname rule and per-install target group. Current CMS creates port 80/443 listeners with fixed priorities, conflicting with the shared platform.
- Remove fixed ECS service name `cms` and task family `cms`; use CloudFormation-generated identifiers. Avoid fixed target-group names and reserve listener priorities through the host's control plane.
- Require versioned/digest-pinned CMS and Apache images from the same approved release. Current defaults use `latest`.
- Use only the application security group on task ENIs. Current template also attaches the public ALB group, whose rules should not be inherited by tasks. Restrict ALB-to-task ingress to the UI port and run tasks on private subnets with explicit egress connectivity.
- Mount the same tenant EFS access point into PHP and Apache with transit encryption and IAM authorization. Current template mounts the client volume only in PHP, and uses a whole filesystem without tenant access-point isolation.
- Supply per-tenant SQL and Mongo credentials through ECS secret references. Current template puts passwords in plain task environment properties and grants execution-role Secrets Manager access to `*`.
- Current runtime database settings and initialization must be checked for unique tenant SQL and Mongo database names, Mongo authentication, Redis isolation and TLS/DocumentDB compatibility. Sharing a host does not authorize sharing credentials or application data.
- Pass APP_PUBLIC_URL, APP_SECRET, SSO settings, and the native Cloud connection through the same supported image initialization path as the Helm deployment.
- Make repository credentials conditional; an empty Docker Hub secret must not be sent to ECS when pulling approved ECR images.
- Scope logs, ECR pull, EFS and secret permissions. Keep Marketplace entitlement permissions only for the Marketplace delivery option.
- Application stacks own their service, rule, target group, secret references and tenant storage. Deletion cannot remove host cluster, shared ALB, RDS or DocumentDB servers. Preserve application data on failed deployment/rollback.

No running stack, database, CMS source, or IAM role was changed by this review. The Cloud Fargate adapter and per-tenant database provisioning are still required; the draft catalog listing must not be published until install/update/delete and cross-organization isolation are tested.

AWS reference: https://docs.aws.amazon.com/eks/latest/userguide/fargate.html — EKS Fargate does not support EBS-backed pods or DaemonSets, so the existing CMS Helm chart cannot be assumed compatible without reviewing its storage and dependencies.

## CMS Serverless release contract

CMS Serverless is a separate catalog item, linked to the CMS repository. Its version has one resource URL, `solodev-cms-serverless.yaml`, published by the CMS tag pipeline. CMS for EKS retains its existing Helm wrapper and resource URL.

AppHub 0.1.8 adds CloudFormation-owned tenant DocumentDB allocation and Valkey group membership. Each application receives a database-specific `readWrite` document user and an authenticated cache user restricted to its stack-name key prefix. Administrator secrets are available only to the allocator. The CMS template owns its tenant secrets, cache user, EFS access point, ECS service and listener rule; the host owns the shared infrastructure. SQL and document data are retained on application rollback/deletion pending a reviewed data lifecycle.

The platform update must be applied through its official versioned CloudFormation change set before launching CMS Serverless. Tenant allocation tests and AWS template validation pass locally; a live CMS Serverless install/update/delete and cross-tenant data test are still required.

Tenant namespace contract v2 uses the application StackId hash for database names,
file roots and Redis prefixes. Reusing a deleted stack name never reuses its data
namespace. The platform advertises `TenantNamespaceV2`; CMS versions requiring it
must not launch against an older allocator. Retained secrets use the stack UUID.
Allocator artifact keys are baked into each published platform template so a
normal upgrade updates its code while preserving customer-selected parameters.
