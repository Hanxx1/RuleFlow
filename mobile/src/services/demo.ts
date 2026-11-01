export type Block={id:string;source_name:string;text:string;page?:number;locator?:string;confidence:number}
export type Profile={student_type?:string;enrollment_year?:number;college?:string;major?:string;class_name?:string;moral_bonus_items?:string[]}

const get=async(name:string)=>{
 const response=await fetch(`/demo/${name}`)
 if(!response.ok)throw Error(`离线示例数据读取失败：${name}`)
 return response.json()
}

const truth=(ast:any,p:Profile):'TRUE'|'FALSE'|'UNKNOWN'=>{if(['and','or','not'].includes(ast.op)){const v=ast.args.map((x:any)=>truth(x,p));if(ast.op==='not')return v[0]==='TRUE'?'FALSE':v[0]==='FALSE'?'TRUE':'UNKNOWN';if(ast.op==='and')return v.includes('FALSE')?'FALSE':v.every((x:string)=>x==='TRUE')?'TRUE':'UNKNOWN';return v.includes('TRUE')?'TRUE':v.every((x:string)=>x==='FALSE')?'FALSE':'UNKNOWN'}const actual=(p as any)[ast.field.replace('profile.','')];if(actual===undefined||actual===null||actual==='')return 'UNKNOWN';if(ast.op==='exists')return 'TRUE';const ok=ast.op==='in'?ast.value.includes(actual):ast.op==='gte'?actual>=ast.value:ast.op==='lte'?actual<=ast.value:actual===ast.value;return ok?'TRUE':'FALSE'}

function ensureEvidence(items:any[],evidenceIds:Set<string>,label:string){
 for(const item of items){
  const refs=item.evidence_ids||item.evidence||[]
  if(!refs.length||refs.some((id:string)=>!evidenceIds.has(id)))throw Error(`${label}缺少有效 EvidenceRef：${item.id||item.title}`)
 }
}

export async function loadDemo(profile:Profile){
 const names=['notice.json','blocks.json','rules.json','tasks.json','materials.json','facts.json','schedule.json']
 const [notice,blocks,rules,tasks,materials,facts,schedule]=await Promise.all(names.map(get))
 const evidenceIds=new Set<string>(blocks.map((item:Block)=>item.id))
 const normalizedTasks={...tasks,nodes:tasks.nodes.map((item:any)=>({...item,evidence_ids:item.evidence_ids||item.evidence||[]}))}
 ensureEvidence(normalizedTasks.nodes,evidenceIds,'演示任务')
 ensureEvidence(materials,evidenceIds,'演示材料')
 ensureEvidence(schedule,evidenceIds,'演示日程')
 const evals=rules.map((rule:any)=>({...rule,value:truth(rule.ast,profile)}))
 const scope=evals[0],bonus=evals[1]
 const byId=(ids:string[])=>blocks.filter((block:Block)=>ids.includes(block.id))
 return {
  notice,blocks,rules:evals,tasks:normalizedTasks,materials,facts,schedule,
  analysis:{summary:'这是与账户数据隔离的离线演示，已整理规则、材料、步骤和本周安排。',questions:['请按实际情况核对德育加分项目；当前演示画像未填写该字段。'],review_reasons:['所有内容均为模拟/脱敏示例，不代表真实通知。']},
  relevance:scope.value==='TRUE'?'相关':scope.value==='FALSE'?'不相关':'待确认',
  scopeEvidence:byId(scope.ast.args.flatMap((item:any)=>item.evidence||[])),bonusUnknown:bonus.value==='UNKNOWN',bonusEvidence:byId(bonus.ast.evidence||[])
 }
}

export async function loadPublicDemos(){
 const bundles=await get('public-cases.json');
 if(!Array.isArray(bundles))throw Error('公开演示样例格式无效');
 for(const bundle of bundles){
  if(!bundle.id?.startsWith('demo-public-'))throw Error('公开演示标识无效');
  const refs=new Set<string>(bundle.blocks.map((block:Block)=>block.id));
  ensureEvidence(bundle.tasks.nodes,refs,'公开演示任务');
  ensureEvidence(bundle.materials,refs,'公开演示材料');
 }
 return bundles;
}
