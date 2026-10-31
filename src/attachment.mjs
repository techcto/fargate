export function attachmentFromOutputs(outputs) {
  const required = ['Cluster', 'ClusterArn', 'ListenerArn', 'LoadBalancerSecurityGroup', 'VpcId'];
  for (const key of required) {
    if (!outputs[key]) throw new Error(`Missing platform output ${key}; update the platform through a reviewed change set.`);
  }
  return { version: 1, engine: 'fargate', platform: 'Fargate App Hub', parameters: Object.fromEntries(required.map(key => [key, outputs[key]])) };
}
