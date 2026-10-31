import test from 'node:test';import assert from 'node:assert/strict';
import {assertStableStack,recoverParameters} from '../src/recovery.mjs';
test('recovery only exports stable stacks',()=>{
 for(const status of['CREATE_COMPLETE','UPDATE_COMPLETE','IMPORT_COMPLETE'])assert.doesNotThrow(()=>assertStableStack(status));
 for(const status of['DELETE_IN_PROGRESS','UPDATE_IN_PROGRESS','ROLLBACK_FAILED'])assert.throws(()=>assertStableStack(status));
});
test('secrets require private input; public values come from deployed state',()=>{
 const template={Parameters:{Secret:{NoEcho:true},Domain:{Type:'String'}}};
 const deployed=[{ParameterKey:'Secret',ParameterValue:'****'},{ParameterKey:'Domain',ParameterValue:'service.example.test'}];
 assert.throws(()=>recoverParameters(template,deployed,[]),/Secret/);
 const result=recoverParameters(template,deployed,[{ParameterKey:'Secret',ParameterValue:'synthetic-test-only'},{ParameterKey:'Domain',ParameterValue:'stale.example.test'}]);
 assert.equal(result[0].ParameterValue,'synthetic-test-only');assert.equal(result[1].ParameterValue,'service.example.test');
});
test('masked secrets cannot be mistaken for recoverable credentials',()=>{
 for(const value of['*','****','********'])assert.throws(()=>recoverParameters({Parameters:{Secret:{NoEcho:true}}},[{ParameterKey:'Secret',ParameterValue:'****'}],[{ParameterKey:'Secret',ParameterValue:value}]));
});
test('public wildcard settings are not treated as masked secrets',()=>{
 const result=recoverParameters({Parameters:{CorsAllowedOrigins:{Type:'String'}}},[{ParameterKey:'CorsAllowedOrigins',ParameterValue:'*'}],[]);
 assert.equal(result[0].ParameterValue,'*');
});
