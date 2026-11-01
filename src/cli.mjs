import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { attachmentFromOutputs } from './attachment.mjs';

if (existsSync('.env')) process.loadEnvFile('.env');
const region = process.env.AWS_REGION || 'us-east-1';
const profile = process.env.AWS_PROFILE;
// Keep the historical default so a display rename never creates another platform.
const stack = process.env.OPEN_FARGATE_STACK_NAME || process.env.APPHUB_STACK_NAME || 'apphub-platform';
const command = process.argv[2] || 'status';
const flags = ['--region', region, ...(profile ? ['--profile', profile] : [])];
function aws(args) {
  const output = execFileSync('aws', [...args, ...flags, '--output', 'json'], { encoding: 'utf8' });
  return output.trim() ? JSON.parse(output) : { submitted: true };
}
function print(value) { console.log(JSON.stringify(value, null, 2)); }
const template = resolve('devops/cloudformation/apphub.yaml');
if (['status', 'outputs', 'attachment'].includes(command)) {
  const deployed = aws(['cloudformation', 'describe-stacks', '--stack-name', stack]).Stacks[0];
  const outputs = Object.fromEntries((deployed.Outputs ?? []).map(v => [v.OutputKey, v.OutputValue]));
  print(command === 'attachment' ? attachmentFromOutputs(outputs) : command === 'outputs' ? outputs : {
    name: deployed.StackName, status: deployed.StackStatus, platform: 'Fargate App Hub', engine: 'fargate'
  });
} else if (command === 'catalog' || command === 'contract') {
  console.log(readFileSync(command === 'catalog' ? 'configs/apps.json' : 'configs/hosting-contract.json', 'utf8'));
} else if (command === 'validate') {
  print(aws(['cloudformation', 'validate-template', '--template-body', JSON.stringify(JSON.parse(readFileSync(template, 'utf8')))]));
} else if (command === 'plan') {
  const [type, name, file] = process.argv.slice(3);
  if (!['CREATE', 'UPDATE'].includes(type) || !name || !file) throw new Error('Usage: bash open-fargate.sh plan CREATE|UPDATE change-set-name private.parameters.json');
  print(aws(['cloudformation', 'create-change-set', '--stack-name', stack, '--change-set-name', name,
    '--change-set-type', type, '--template-body', JSON.stringify(JSON.parse(readFileSync(template, 'utf8'))), '--parameters', 'file://' + resolve(file), '--capabilities', 'CAPABILITY_IAM']));
} else if (command === 'plan-app') {
  const [type, appStack, name, templateFile, file] = process.argv.slice(3);
  if (!['CREATE', 'UPDATE'].includes(type) || !appStack || !name || !templateFile || !file) {
    throw new Error('Usage: bash open-fargate.sh plan-app CREATE|UPDATE app-stack change-set template private.parameters.json');
  }
  if (appStack === stack) throw new Error('An application must not replace the backing platform stack.');
  const deployed = aws(['cloudformation', 'describe-stacks', '--stack-name', stack]).Stacks[0];
  if (!['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'].includes(deployed.StackStatus)) {
    throw new Error('The backing platform must be stable before preparing an application change set.');
  }
  const outputs = Object.fromEntries((deployed.Outputs ?? []).map(v => [v.OutputKey, v.OutputValue]));
  attachmentFromOutputs(outputs);
  const supplied = JSON.parse(readFileSync(file, 'utf8'));
  if (!Array.isArray(supplied)) throw new Error('Use an AWS CloudFormation parameters array.');
  const bound = ['Cluster', 'ListenerArn', 'LoadBalancerSecurityGroup', 'VpcId'];
  const seen = new Set();
  for (const parameter of supplied) {
    if (!parameter || typeof parameter.ParameterKey !== 'string' || seen.has(parameter.ParameterKey)) {
      throw new Error('Parameters must have unique ParameterKey values.');
    }
    seen.add(parameter.ParameterKey);
    if (bound.includes(parameter.ParameterKey)) throw new Error('Backing platform parameters are resolved from its stack, not application input.');
  }
  const parameters = [...supplied, ...bound.map(key => ({ ParameterKey: key, ParameterValue: outputs[key] }))];
  print(aws(['cloudformation', 'create-change-set', '--stack-name', appStack, '--change-set-name', name,
    '--change-set-type', type, '--template-body', 'file://' + resolve(templateFile),
    '--parameters', JSON.stringify(parameters), '--capabilities', 'CAPABILITY_IAM']));
} else if (command === 'review-app' || command === 'execute-app') {
  const [appStack, name, confirmation] = process.argv.slice(3);
  if (!appStack || appStack === stack || !name) throw new Error('Use the application stack name and change-set name.');
  if (command === 'execute-app' && confirmation !== '--reviewed') throw new Error('Review the application change set before using --reviewed.');
  print(aws(['cloudformation', command === 'review-app' ? 'describe-change-set' : 'execute-change-set',
    '--stack-name', appStack, '--change-set-name', name]));
} else if (command === 'review' || command === 'execute') {
  const name = process.argv[3];
  if (!name) throw new Error('A reviewed change-set name is required.');
  if (command === 'execute' && process.argv[4] !== '--reviewed') throw new Error('Review replacements, deletions, and availability before using execute NAME --reviewed.');
  print(aws(['cloudformation', command === 'review' ? 'describe-change-set' : 'execute-change-set', '--stack-name', stack, '--change-set-name', name]));
} else {
  throw new Error('Commands: status, outputs, attachment, contract, catalog, validate, plan, review, execute. Direct create is retired; use a CREATE change set.');
}
