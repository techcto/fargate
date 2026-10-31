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
  print(aws(['cloudformation', 'validate-template', '--template-body', 'file://' + template]));
} else if (command === 'plan') {
  const [type, name, file] = process.argv.slice(3);
  if (!['CREATE', 'UPDATE'].includes(type) || !name || !file) throw new Error('Usage: bash open-fargate.sh plan CREATE|UPDATE change-set-name private.parameters.json');
  print(aws(['cloudformation', 'create-change-set', '--stack-name', stack, '--change-set-name', name,
    '--change-set-type', type, '--template-body', 'file://' + template, '--parameters', 'file://' + resolve(file)]));
} else if (command === 'review' || command === 'execute') {
  const name = process.argv[3];
  if (!name) throw new Error('A reviewed change-set name is required.');
  if (command === 'execute' && process.argv[4] !== '--reviewed') throw new Error('Review replacements, deletions, and availability before using execute NAME --reviewed.');
  print(aws(['cloudformation', command === 'review' ? 'describe-change-set' : 'execute-change-set', '--stack-name', stack, '--change-set-name', name]));
} else {
  throw new Error('Commands: status, outputs, attachment, contract, catalog, validate, plan, review, execute. Direct create is retired; use a CREATE change set.');
}
