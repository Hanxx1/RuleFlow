import {evaluate,type Truth} from './rules';
import {resolvedFacts,type Workspace} from './clientWorkspace';
function fields(ast:any,depth=0):string[]{if(depth>32)return [];return ast?.field?[ast.field.replace('profile.','')]:Array.isArray(ast?.args)?ast.args.flatMap((x:any)=>fields(x,depth+1)):[]}
export function matchLocal(resources:any,workspace:Workspace,caseId:string,today?:string){
 const resolved=resolvedFacts(workspace,caseId,today),sourceRefs=new Set((resources.evidence||[]).map((e:any)=>e.id));
 const rows=(resources.rules||[]).filter((r:any)=>r.kind!=='action_trigger').map((rule:any)=>{
  const required=[...new Set(fields(rule.ast))];const refs=rule.evidence_ids||rule.ast?.evidence||[];let value:Truth='UNKNOWN';
  if(refs.length&&refs.every((id:string)=>sourceRefs.has(id))){try{value=evaluate(rule.ast,resolved.facts)}catch{value='UNKNOWN'}}
  return {id:rule.id,label:rule.label||rule.title||'条件',value,required,missing:required.filter(k=>!(k in resolved.facts)),ruleEvidence:refs.filter((id:string)=>sourceRefs.has(id)),profileEvidence:required.flatMap(k=>resolved.evidence[k]||[])};
 });
 const unsupported=resources.evaluation?.unsupported_conditions||[];const missingAttachments=resources.attachments?.missing_count||0;
 const relevance:Truth=rows.some((r:any)=>r.value==='FALSE')?'FALSE':!rows.length||rows.some((r:any)=>r.value==='UNKNOWN')||unsupported.length||missingAttachments?'UNKNOWN':'TRUE';
 return {relevance,missingAttachments,reason:missingAttachments?'missing_attachments':resolved.conflicts.length?'profile_conflict':unsupported.length?'unmodeled_conditions':!rows.length?'insufficient_evidence':rows.some((r:any)=>r.missing.length)?'missing_profile_fact':'supported_rules',rows,unsupported,conflicts:resolved.conflicts,revision:workspace.revision,facts:resolved.facts};
}
