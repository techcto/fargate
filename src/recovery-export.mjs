import {execFileSync} from 'node:child_process';
import {existsSync,readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {assertStableStack,recoverParameters} from './recovery.mjs';
if(existsSync('.env'))process.loadEnvFile('.env');
const [stack,privateParameters,bundle]=process.argv.slice(2);
if(!stack||!privateParameters||!bundle)throw new Error('Usage: node src/recovery-export.mjs <stack> <private.parameters.json> <new-bundle-directory>');
const target=resolve(bundle);
if(existsSync(target))throw new Error('Refusing to overwrite a recovery bundle');
const flags=['--region',process.env.AWS_REGION||'us-east-1',...(process.env.AWS_PROFILE?['--profile',process.env.AWS_PROFILE]:[])];
const aws=args=>JSON.parse(execFileSync('aws',[...args,...flags,'--output','json'],{encoding:'utf8'}));
const deployed=aws(['cloudformation','describe-stacks','--stack-name',stack]).Stacks[0];
assertStableStack(deployed.StackStatus);
const template=aws(['cloudformation','get-template','--stack-name',stack]).TemplateBody;
if(typeof template!=='object')throw new Error('This exporter requires a JSON CloudFormation template');
const launch=JSON.parse(readFileSync(privateParameters,'utf8'));
const parameters=recoverParameters(template,deployed.Parameters,launch);
const inventory=aws(['cloudformation','list-stack-resources','--stack-name',stack]).StackResourceSummaries;
execFileSync('mkdir',['-p',target]);
const files={
 'template.json':template,
 'launch.parameters.json':parameters,
 'inventory.local.json':{stack,status:deployed.StackStatus,exportedAt:new Date().toISOString(),resources:inventory,outputs:deployed.Outputs},
 'README.txt':'Private configuration recovery bundle. This is NOT a database or object-content backup. Protect launch.parameters.json as a secret. Use RECOVERY.md for CloudFormation-only retain, relaunch, handoff, and ownership import. Never blindly CREATE the template against retained storage.\n'
};
for(const[name,value]of Object.entries(files)){
 const content=typeof value==='string'?value:JSON.stringify(value,null,2)+'\n';
 execFileSync('apply_patch',[],{input:'*** Begin Patch\n*** Add File: '+join(target,name)+'\n'+content.trimEnd().split('\n').map(l=>'+'+l).join('\n')+'\n*** End Patch\n'});
 execFileSync('chmod',['600',join(target,name)]);
}
execFileSync('chmod',['700',target]);
console.log('Private configuration recovery bundle exported. Application content is not included.');
