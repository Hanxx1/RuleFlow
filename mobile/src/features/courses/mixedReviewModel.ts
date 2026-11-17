// CM-007 presentation state only. These sample references are never server EvidenceRef or execution DTOs.
export type MixedKind='requirement'|'task'|'case'|'knowledge';
export type MixedOperation='create'|'update'|'link'|'ignore';
export type MixedStatus='pending'|'success'|'failed'|'unknown'|'blocked'|'ignored';
export type MixedCandidate={id:string;kind:MixedKind;title:string;content:string;sourceId:string;quote:string;target:string;operation:MixedOperation;selected:boolean;acknowledged:boolean;eligibility:'UNKNOWN'|'TRUE';missingFields:string[];dependsOn:string[];existing?:{target:string;title:string;value:string};version:number;attempts:number;status:MixedStatus;message:string};
export type MixedReview={courses:{id:string;name:string;term:string}[];sources:{id:string;text:string}[];items:MixedCandidate[]};
export const kindLabels:Record<MixedKind,string>={requirement:'课程要求',task:'课程任务',case:'校园事务',knowledge:'知识资料'};
export const operationLabels:Record<MixedOperation,string>={create:'新增',update:'更新已有要求',link:'关联已有记录',ignore:'忽略'};
export const statusLabels:Record<MixedStatus,string>={pending:'待核对',success:'样例成功',failed:'样例失败',unknown:'结果未知',blocked:'暂不能执行',ignored:'已忽略'};
const copy=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
export function allowedOperations(item:MixedCandidate):MixedOperation[]{return ['create',...(item.existing?.target===item.target?[item.kind==='requirement'?'update' as const:'link' as const]:[]),'ignore']}
export function reviewIssue(review:MixedReview,item:MixedCandidate):string {
  if(item.operation==='ignore')return '';
  const source=review.sources.find(source=>source.id===item.sourceId);
  if(!source||!item.quote.trim()||!source.text.includes(item.quote))return '来源缺失或原句不符，待核对，不能执行';
  if(!item.content.trim()||item.content.length>2000||!item.title.trim())return '请补充有效内容（最多 2000 字）';
  if(item.kind==='case'?item.target!=='campus':!review.courses.some(course=>course.id===item.target))return '请核对建议归属';
  if(!allowedOperations(item).includes(item.operation))return '所选操作没有可关联的对应记录';
  if(item.dependsOn.some(id=>{const parent=review.items.find(other=>other.id===id);return !parent||parent.target!==item.target}))return '前置建议的归属已不一致，请重新核对关联';
  if(item.existing?.target===item.target&&!item.acknowledged)return '请先核对现有记录及本次操作';
  return '';
}
export function editMixedItem(review:MixedReview,id:string,patch:Partial<Pick<MixedCandidate,'selected'|'target'|'operation'|'content'|'acknowledged'>>):MixedReview {
  const current=review.items.find(item=>item.id===id);
  if(!current)throw Error('建议已失效');
  if(current.status==='success'||current.status==='unknown')throw Error('已完成或结果未知的建议不能改写，请先核对结果');
  const next=copy(review),item=next.items.find(item=>item.id===id)!;
  const changed=(patch.target!==undefined&&patch.target!==item.target)||(patch.operation!==undefined&&patch.operation!==item.operation)||(patch.content!==undefined&&patch.content!==item.content);
  Object.assign(item,patch);
  if(changed){item.version++;item.acknowledged=false;item.status='pending';item.message='内容或归属已改变，请重新核对';if(!allowedOperations(item).includes(item.operation))item.operation='create'}
  return next;
}
export type SampleScenario='partial'|'unknown';
export function simulateMixedReview(review:MixedReview,ids:string[],scenario:SampleScenario):MixedReview {
  if(new Set(ids).size!==ids.length||ids.some(id=>!review.items.some(item=>item.id===id)))throw Error('建议选择无效');
  const next=copy(review);
  let pending=next.items.filter(item=>ids.includes(item.id)&&item.selected&&item.status!=='success'&&item.status!=='unknown');
  // Separate sample operations may finish independently; this is not a Task dependency graph or a transaction.
  for(let round=0;round<=next.items.length&&pending.length;round++){
    let progressed=false;
    pending=pending.filter(item=>{
      if(item.operation==='ignore'){item.status='ignored';item.message='未执行任何操作';progressed=true;return false}
      const issue=reviewIssue(next,item);
      if(issue){item.status='blocked';item.message=issue;return false}
      if(item.dependsOn.some(id=>next.items.find(other=>other.id===id)?.status!=='success'))return true;
      item.attempts++;progressed=true;
      if(item.id==='sample-code-task'&&item.attempts===1){item.status=scenario==='unknown'?'unknown':'failed';item.message=scenario==='unknown'?'模拟响应丢失，先查询样例回执，不能直接重发':'模拟服务暂时不可用，可单独重试'}
      else{item.status='success';item.message='仅记录本页模拟回执，未写入正式数据'}
      return false;
    });
    if(!progressed)break;
  }
  for(const item of pending){item.status='blocked';item.message='前置建议尚未成功，请先处理前置项，再继续本项'}
  return next;
}
export function resolveSampleReceipt(review:MixedReview,id:string):MixedReview {
  const next=copy(review),item=next.items.find(item=>item.id===id);
  if(!item||item.status!=='unknown')throw Error('没有需要查询的样例回执');
  item.status='success';item.message='样例查询确认首次已完成，未再次执行';return next;
}
