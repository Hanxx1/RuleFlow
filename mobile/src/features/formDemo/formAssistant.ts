import {api,ApiError} from '../../core/http'
import {loadWorkspace,resolvedFacts} from '../../services/clientWorkspace'
import {profileLabels} from '../../services/profileLabels'
import {experienceKinds,loadExperiences} from '../experience/archive'
import {formTextLength,type Field} from './scenarios'
import {readTextLimits} from './formFields'

export type Source = {
  id:string;kind:'notice'|'original'|'profile'|'experience'|'material'|'answer';locator:string;text:string
}
export type AssistField = {
  id:string;label:string;source_id:string;writable:boolean;locked:boolean
  choices?:readonly string[];min_chars?:number;max_chars?:number
}
export type Cite = {source_id:string;quote:string}
export type Plan = {
  id:string;meaning:string;expected:string
  data_type:'text'|'long_text'|'integer'|'decimal'|'date'|'choice'|'multiple'|'open'
  role:'applicant'|'other'|'unknown'
  required:'required'|'optional'|'conditional'|'unknown'
  condition?:string|null;applicability:'applies'|'not_applicable'|'unknown'
  strategy:'direct'|'retrieve'|'derive'|'integrate'|'generate'|'ask'|'manual'|'skip'
  bounds:{min_chars?:number|null;max_chars?:number|null;format_note?:string|null
    earliest_date?:string|null;latest_date?:string|null;minimum_number?:number|null;maximum_number?:number|null}
  ambiguous:boolean;requirements:Cite[];facts:Cite[];value?:string|null
  calculation?:{operation:'days_between'|'inclusive_days'|'integer_sum'|'count';operands:Cite[]}|null
}
export type Question = {text:string;fields:string[]}
export type Approved = {fieldId:string;plan:Plan;value:string;references:Source[]}

export async function accountFacts(owner:string,caseId:string):Promise<Source[]> {
  const [workspace,experiences] = await Promise.all([loadWorkspace(owner),loadExperiences(owner)])
  const {facts,evidence} = resolvedFacts(workspace,caseId)
  return [
    ...Object.entries(facts).map(([id,value]):Source=>({
      id:evidence[id][0].id,kind:'profile',locator:'已确认画像 · '+(profileLabels[id] || id),
      text:typeof value==='string' ? value : JSON.stringify(value),
    })),
    ...experiences.filter(entry=>entry.confirmed).map((entry):Source=>({
      id:'experience:'+entry.id+':'+entry.revision,kind:'experience',locator:'已确认'+experienceKinds[entry.kind]+' · '+entry.title,
      text:[entry.title,entry.month,entry.endMonth,entry.issuer,entry.level,entry.role,
        entry.contribution,entry.result,entry.hours && entry.hours+' 小时'].filter(Boolean).join(' · '),
    })),
  ]
}

const day = (value:string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN
  const stamp = Date.parse(value+'T00:00:00Z')
  return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0,10)===value ? stamp / 86400000 : NaN
}

export function proposedValue(plan:Plan):string {
  if (plan.role!=='applicant' || plan.ambiguous || plan.applicability!=='applies') return ''
  if (!plan.calculation) return plan.value || ''
  const {operation,operands} = plan.calculation
  const values = operands.map(operand=>operand.quote)
  const unique = new Set(operands.map(operand=>JSON.stringify([operand.source_id,operand.quote])))
  if (unique.size!==operands.length) return ''
  if (operation==='count') return String(values.length)
  if (operation==='integer_sum' && values.every(value=>/^-?\d{1,9}$/.test(value))) {
    return String(values.reduce((sum,value)=>sum+Number(value),0))
  }
  if ((operation==='days_between' || operation==='inclusive_days') && values.length===2) {
    const difference = day(values[1])-day(values[0])
    if (Number.isFinite(difference) && difference>=0) return String(difference+(operation==='inclusive_days'?1:0))
  }
  return ''
}

export function checkAssistantValue(field:Field,plan:Plan,value:string) {
  const exact = plan.requirements.map(item=>readTextLimits(item.quote))
  const evidencedMin = exact.flatMap(limit=>limit.min===undefined ? [] : [limit.min])
  const evidencedMax = exact.flatMap(limit=>limit.max===undefined ? [] : [limit.max])
  const explicit = field.min!==undefined || field.max!==undefined || evidencedMin.length>0 || evidencedMax.length>0
  const min = Math.max(field.min ?? 0,...evidencedMin,explicit ? 0 : plan.bounds.min_chars ?? 0)
  const max = Math.min(field.max ?? Infinity,...evidencedMax,explicit ? Infinity : plan.bounds.max_chars ?? Infinity)
  const text = value.trim()
  if (min>max) return '字数要求冲突，请核对原表和通知。'
  if (plan.role!=='applicant' || plan.ambiguous || plan.applicability==='unknown') return '填写主体或适用条件待核对。'
  if (plan.applicability==='not_applicable') return text ? '已标为不适用，请核对填写内容。' : ''
  if (!text) return plan.required==='required' || plan.required==='conditional' ? '请先补齐此字段。' : ''
  if (formTextLength(text)<min) return '至少填写 '+min+' 字。'
  if (formTextLength(text)>max) return '最多填写 '+max+' 字。'
  if (text.length>2000) return '此 Office 写入位置最多支持 2000 个 UTF-16 字符。'
  if (field.choices && !field.choices.includes(text)) return '请选择原表允许的选项。'
  if (plan.data_type==='integer' && !/^-?\d+$/.test(text)) return '请填写整数。'
  if (plan.data_type==='decimal' && !/^-?\d+(?:\.\d+)?$/.test(text)) return '请填写有效数字。'
  if (plan.data_type==='date') {
    const date=day(text)
    if (!Number.isFinite(date)) return '请填写有效日期（年-月-日）。'
    if (plan.bounds.earliest_date && !(date>=day(plan.bounds.earliest_date))) return '请核对日期下限。'
    if (plan.bounds.latest_date && !(date<=day(plan.bounds.latest_date))) return '请核对日期上限。'
  }
  if (plan.data_type==='integer' || plan.data_type==='decimal') {
    const number=Number(text)
    if (!Number.isFinite(number)) return '请填写有限数值。'
    if (plan.bounds.minimum_number!=null && number<plan.bounds.minimum_number) return '小于已确认的数值下限。'
    if (plan.bounds.maximum_number!=null && number>plan.bounds.maximum_number) return '大于已确认的数值上限。'
  }
  return ''
}

export async function requestFormAssistant(stage:'analyze'|'generate', attachment:string, fields:AssistField[],
                                           sources:Source[], signal:AbortSignal) {
  const result:{fields:Plan[];questions:Question[]} = await api('/api/v1/form-assistant',{
    method:'POST',signal,body:JSON.stringify({stage,attachment,fields,sources,consent:true}),
  })
  return result
}

export function assistantError(error:unknown) {
  const code = error instanceof ApiError ? error.code : ''
  return ({
    FORM_AI_INVALID_INPUT:'本次发送的字段或资料超出接口范围，请减少资料后重试。',
    FORM_AI_UNCONFIGURED:'模型服务尚未配置，可继续手工填写。',
    FORM_AI_UNAVAILABLE:'模型服务暂不可用，可继续填写或稍后重试。',
    FORM_AI_INVALID_OUTPUT:'模型返回的字段或原文依据无法核验，本次未带入内容。',
    FORM_AI_INPUT_LIMIT:'本次发送的资料过长，请减少所选材料或缩短摘录。',
  } as Record<string,string>)[code || ''] || (error instanceof ApiError && error.status===401
    ? '登录已失效，请重新登录后使用智能填写。' : '智能填写暂时失败，可继续手工填写。')
}
