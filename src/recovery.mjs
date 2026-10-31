export function assertStableStack(status){
 if(!['CREATE_COMPLETE','UPDATE_COMPLETE','IMPORT_COMPLETE'].includes(status))throw new Error('Export only a stable application stack');
}
export function recoverParameters(template,deployed,launch){
 const values=new Map(launch.map(p=>[p.ParameterKey,p.ParameterValue]));
 return deployed.map(p=>{
  const secret=template.Parameters?.[p.ParameterKey]?.NoEcho;
  const value=secret?values.get(p.ParameterKey):p.ParameterValue;
  if(typeof value!=='string'||(secret&&/^\*+$/.test(value)))throw new Error('Missing unmasked private launch parameter: '+p.ParameterKey);
  return {ParameterKey:p.ParameterKey,ParameterValue:value};
 });
}
