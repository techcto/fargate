# Application backup and recovery job

All installation, migration, restore infrastructure, and removal must be managed through formal CloudFormation templates and reviewed change sets. No direct resource deletion or manual restore provisioning.

## Preserve-and-relaunch workflow

Export a private configuration recovery bundle after a successful deployment:

```sh
node src/recovery-export.mjs APP_STACK path/to/private.parameters.json backups/APP_STACK-recovery
```

The exporter rejects unstable stacks, refuses to overwrite bundles, and requires unmasked private launch parameters for secrets. `backups/` is ignored. Store bundles encrypted outside the repository and verify they can be read before a migration.

1. Export the deployed template, resource inventory, private launch parameters, and current shared-infrastructure attachment values. Keep credentials in ignored private files, never in templates or public artifacts. Preserve encryption keys and launch secrets so credentials and sessions remain valid.
2. Apply and verify `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` to the storage resources in the source stack. Preserve shared listener certificates during ownership handoff.
3. Create a replacement app stack through a CREATE change set. Its relaunch template references existing storage through parameters and creates independent compute, roles, security groups, target groups, and non-conflicting host-rule priorities.
4. Verify every new ECS service, ALB target, TLS hostname, login, and a representative application operation. Only then switch traffic through a reviewed listener-priority change set.
5. Delete the source stack through CloudFormation. Its retained storage must stay intact. Never delete a source while a replacement is unhealthy.
6. Use an IMPORT change set and the owned-data template to put retained storage under the replacement stack. Review that only storage is imported and no existing compute is modified. Verify physical resource identifiers match the original inventory.
7. Recheck health and data, remove any temporary cleanup stack through CloudFormation, and export a new recovery bundle.

GuardScale and OpenADA each provide `*-apphub-relaunch.yaml` and `*-apphub-owned-data.yaml` templates. Filled parameter files are private and ignored. Relaunch templates reuse storage; owned-data templates complete the subsequent import. Do not use an owned-data template to CREATE new empty storage when recovering existing data.

## Scheduled data backups

`devops/cloudformation/app-backups.yaml` defines a retained AWS Backup vault, daily plan, scoped resource selection, and backup service role. Review selected DynamoDB and S3 ARNs and install it through a CloudFormation change set. S3 versioning and AWS Backup service prerequisites must already be enabled through the owning app template. Verify successful recovery points; creating a plan alone does not prove a backup exists. Redis cache is not selected by this plan.

Retention and configuration exports are not data backups. The migration above preserves existing data but cannot recover deleted or corrupted records. The backup plan is a separate optional deployment and has not been enabled merely by saving this file. Snapshot restoration is not automated here: it requires a reviewed CloudFormation-owned restore implementation followed by data validation and ownership import, not a manual restore API call. Test that recovery path before treating backups as production-ready disaster recovery.
