export function attachmentFromOutputs(outputs) {
  const required = ['Cluster', 'ClusterArn', 'VpcId'];
  for (const key of required) {
    if (!outputs[key]) throw new Error(`Missing platform output ${key}; update the platform through a reviewed change set.`);
  }
  const optional = ['ListenerArn', 'LoadBalancerSecurityGroup', 'DatabaseClusterArn', 'DatabaseEndpoint', 'DatabaseSecurityGroup', 'TenantDatabaseProviderArn', 'PlatformStackName', 'PlatformStackId', 'ServiceSubnets', 'DocumentDbArn', 'DocumentDbEndpoint', 'DocumentDbSecurityGroup', 'EfsFileSystemId', 'EfsSecurityGroup', 'RedisArn', 'RedisHost', 'RedisSecurityGroup', 'RedisUserGroupId', 'BackupPlanId', 'BackupVaultName', 'TaskEventsLogGroup'];
  const available = [...required, ...optional.filter(key => outputs[key])];
  return { version: 1, engine: 'fargate', platform: 'Fargate App Hub', parameters: Object.fromEntries(available.map(key => [key, outputs[key]])) };
}
