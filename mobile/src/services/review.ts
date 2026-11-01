import {api} from '../core/http';

export interface ReviewAction {id:string;title:string;origin?:'document'|'suggestion'|'previous';evidence_ids:string[];evidence_quotes:Record<string,string>;proposed_deadline?:string|null}
export interface ReviewDate {id:string;raw:string;value:string|null;role:string;quote:string;evidence_ids:string[];review_reasons:string[]}
export interface AnalysisReview {revision:number;status:'needs_confirmation'|'confirmed';candidate:{actions:ReviewAction[];dates:ReviewDate[];dependencies?:{before_action_id:string;after_action_id:string;quote:string}[]};decision:unknown}
export interface ReviewSelection {actionIds:string[];deadlineId:string;manualDeadline:string;noDeadline:boolean;consent:boolean;taskDeadlines?:Record<string,{deadline_id?:string;manual_deadline?:string;no_deadline?:boolean}>}

export function confirmationPayload(review:AnalysisReview,selection:ReviewSelection){
  if(!selection.consent)throw Error('请明确确认所选日期和行动步骤。');
  if(Number(Boolean(selection.deadlineId))+Number(Boolean(selection.manualDeadline))+Number(selection.noDeadline)!==1)throw Error('请选择一种截止日期处理方式。');
  if(selection.actionIds.some(id=>!review.candidate.actions.some(action=>action.id===id)))throw Error('候选已发生变化，请重新读取。');
  return {revision:review.revision,action_ids:selection.actionIds,deadline_id:selection.deadlineId||null,manual_deadline:selection.manualDeadline||null,no_deadline:selection.noDeadline,consent:true,...(selection.taskDeadlines?{task_deadlines:selection.taskDeadlines}:{})};
}
export const loadReview=(caseId:string):Promise<AnalysisReview|null>=>api(`/api/v1/cases/${caseId}/reviews`).then(value=>value?.revision?value:null);
export const prepareLegacyReview=(caseId:string):Promise<AnalysisReview>=>api(`/api/v1/cases/${caseId}/reviews/prepare`,{method:'POST'});
export const submitReview=(caseId:string,review:AnalysisReview,selection:ReviewSelection):Promise<AnalysisReview>=>api(`/api/v1/cases/${caseId}/confirm`,{method:'POST',body:JSON.stringify(confirmationPayload(review,selection))});
