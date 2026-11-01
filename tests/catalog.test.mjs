import{test}from'node:test';import assert from'node:assert/strict';import{readFileSync}from'node:fs';
const catalog=JSON.parse(readFileSync(new URL('../configs/apps.json',import.meta.url),'utf8'));
test('all app routes have unique priorities and API precedes web',()=>{const seen=new Set();for(const app of catalog.apps){assert.ok(app.apiPriority<app.webPriority);for(const p of [app.apiPriority,app.webPriority]){assert.ok(p>=1&&p<=49999);assert.ok(!seen.has(p));seen.add(p)}}});
test('domains and app identifiers are unique; Osirus remains separate',()=>{for(const key of ['id','domain'])assert.equal(new Set(catalog.apps.map(a=>a[key])).size,catalog.apps.length);assert.ok(!catalog.apps.some(a=>a.id==='osirus'));assert.ok(catalog.excluded.includes('osirus'))});
test('shared platform owns no app databases or application services',()=>{const template=JSON.parse(readFileSync(new URL('../devops/cloudformation/apphub.yaml',import.meta.url),'utf8'));const types=Object.values(template.Resources).map(v=>v.Type);assert.ok(types.includes('AWS::ECS::Cluster'));assert.equal(types.filter(t=>t==='AWS::ElasticLoadBalancingV2::LoadBalancer').length,1);assert.ok(!types.includes('AWS::ECS::Service'));assert.ok(!types.includes('AWS::DynamoDB::Table'))});

test('Valkey uses native default-user disabling without a dummy password secret',()=>{
  const template=JSON.parse(readFileSync(new URL('../devops/cloudformation/apphub.yaml',import.meta.url),'utf8'));
  assert.equal(template.Resources.RedisUserGroup.Properties.Engine,'valkey');
  assert.equal(template.Resources.RedisUserGroup.Properties.UserIds,undefined);
  assert.equal(template.Resources.RedisDisabledSecret,undefined);
  assert.equal(template.Resources.RedisDisabledDefaultUser,undefined);
  assert.deepEqual(template.Resources.Redis.Properties.UserGroupId,{Ref:'RedisUserGroup'});
  assert.equal(template.Parameters.RedisMode.Default,'None');
  assert.equal(template.Parameters.DocumentDbAdminPassword.NoEcho,true);
  assert.equal(template.Resources.DocumentDbAdminSecret.Properties.GenerateSecretString,undefined);
  assert.match(template.Resources.DocumentDbAdminSecret.Properties.SecretString['Fn::Sub'],/\$\{DocumentDbAdminPassword\}/);
  assert.ok(template.Rules.DocumentDbPasswordRequired);
});

test('product deletion never silently detaches owned AWS resources',()=>{
  const template=JSON.parse(readFileSync(new URL('../devops/cloudformation/apphub.yaml',import.meta.url),'utf8'));
  for(const resource of Object.values(template.Resources)){
    assert.notEqual(resource.DeletionPolicy,'Retain');
    assert.notEqual(resource.UpdateReplacePolicy,'Retain');
  }
  for(const name of ['Database','DatabaseWriter','DocumentDb','DocumentDbWriter','FileSystem','Redis','BackupVault']){
    assert.equal(template.Resources[name].DeletionPolicy,'Delete');
    assert.equal(template.Resources[name].UpdateReplacePolicy,'Delete');
  }
  assert.equal(template.Resources.Database.Properties.DeletionProtection,false);
  assert.equal(template.Resources.DocumentDb.Properties.DeletionProtection,false);
});
