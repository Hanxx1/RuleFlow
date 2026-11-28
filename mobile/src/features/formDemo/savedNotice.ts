import {ApiError,api} from '../../core/http'
import {readFormContext,type FormContext,type FormContextSource} from '../imports/formContext'
import {readFormOriginal} from '../imports/formOriginal'
import {analyzeNotice,isLegacyXls,isPdfAttachment,matchAttachment,noticeTargetMatches,type NoticeEvidence} from './noticeIntake'

export async function loadSavedNotice(batchId: string) {
  const read = async () => {
    const batch = await api('/api/v1/import-batches/'+encodeURIComponent(batchId),{cache:'no-store'})
    return readFormContext(batchId,batch.revision)
  }
  try {
    return await read()
  } catch (error) {
    if (error instanceof ApiError && error.code==='IMPORT_BATCH_STALE') return read()
    throw error
  }
}

export const isOfficeSource = (source: FormContextSource) =>
  /\.(docx|xlsx)$/i.test(source.document_ref?.name || source.name)
export const isLegacyXlsSource = (source:FormContextSource) => isLegacyXls(source.document_ref?.name || source.name)

export const isPdfSource = (source:FormContextSource) => isPdfAttachment(source.document_ref?.name || source.name)

export function originalProblem(source: FormContextSource) {
  if (source.original.state==='missing') return '原件已缺失，请从来源页重新导入。'
  if (source.original.state==='unverified') return '原件状态待核对，请稍后重新读取。'
  if (source.original.state!=='present' || !source.document_ref) return '尚未取得可核验的原件。'
  return ''
}

export async function loadSavedOriginal(snapshot: FormContext,source: FormContextSource) {
  const problem = originalProblem(source)
  const document = source.document_ref
  if (problem || !document) throw Error(problem)
  const blob = await readFormOriginal(snapshot,source.source_id)
  const match = await matchAttachment(new File([blob],document.name,{type:document.mime}),document,true)
  if (match.scenario) return {scenario:match.scenario}
  if (match.generic) return {generic:match.generic}
  throw Error(match.error || '此原表待核对。')
}

export function savedDraftKey(batchId: string,source: FormContextSource) {
  const document = source.document_ref
  return JSON.stringify([batchId,source.source_id,document?.id,document?.revision,document?.sha256])
}

export function defaultNotice(context: FormContext,target: FormContextSource) {
  if (target.parent_reference_state==='missing') return ''
  const candidates = context.sources.filter(source=>source.source_id!==target.source_id &&
    source.extraction.state==='available')
  if (target.parent_reference_state==='valid') {
    return candidates.find(source=>source.source_id===target.parent_source_id)?.source_id || ''
  }
  const primary = candidates.filter(source=>!isLegacyXlsSource(source) &&
    (!isOfficeSource(source) || /通知|公告|通告/.test(source.name)))
  return primary.length===1 ? primary[0].source_id : ''
}

export type ScopeSelection = {applyTo:readonly string[]; candidates:readonly string[]; manual?:boolean}
export type ScopeSelections = Readonly<Record<string,ScopeSelection>>

export function savedRules(context: FormContext,notice: FormContextSource | undefined,
                           targetId: string,selections: ScopeSelections,excluded: readonly string[]) {
  const targets = context.sources.filter(source=>source.source_id!==notice?.source_id &&
    isOfficeSource(source) && !excluded.includes(source.source_id) &&
    (source.parent_reference_state!=='valid' || source.parent_source_id===notice?.source_id))
    .map(source=>({id:source.source_id,name:source.name}))
  const text = notice?.extraction.state==='available' && notice.text && notice.text.length<=30_000 ? notice.text : ''
  const analysis = analyzeNotice(text)
  const displayLines = notice?.lines.flatMap(line=>line.text.split(/\r?\n/).map(()=>line)) || []
  const items = analysis.evidence.map(item=>{
    const line = displayLines[item.line-1]
    const key = JSON.stringify([notice?.source_id,line?.line_id ?? item.line,item.kind,item.text])
    // Suggestions may use labels. Confirmed scope always uses stable source IDs.
    const chosen = selections[key]
    const {references,named} = noticeTargetMatches(item,targets)
    const suggested = references.length===1 ? references[0] : targets.length===1 && !named ? targets[0] : undefined
    const scope = chosen?.applyTo ?? (suggested ? [suggested.id] : undefined)
    const affectsTarget = !references.length || references.some(ref=>ref.id===targetId)
    const needsScope = item.kind!=='review' && !chosen?.manual && affectsTarget && (!scope ||
      Boolean(chosen && !chosen.candidates.includes(targetId) && !scope.includes(targetId)))
    return {...item,key,lineId:line?.line_id,lineNumber:line?.line_number,locator:line?.locator,scope,needsScope,manual:Boolean(chosen?.manual)}
  })
  const selected = items.filter(item=>item.scope?.includes(targetId) ||
    (item.kind==='review' && item.scope===undefined))
  const ids = new Set(selected.map(item=>item.id))
  const requirements = analyzeNotice(text,clause=>ids.has(clause.id))
  const manual = items.filter(item=>item.manual)
  requirements.evidence.push(...manual.map(item=>({...item,kind:'review' as const})))
  const unresolved = items.some(item=>item.needsScope)
  const recognizedLines = new Set(items.map(item=>item.line))
  const otherLines = text.split(/\r?\n/).filter((line,index)=>line.trim() && !recognizedLines.has(index+1))
  // A replaced formal line, a changed applicable clause or a new unresolved rule requires review.
  const signature = JSON.stringify([
    notice?.source_id,unresolved,selected.map(item=>item.key),manual.map(item=>item.key),otherLines,requirements.competitionEvidence?.text,
  ])
  return {items,targets,requirements,unresolved,signature,analysis}
}

export type SavedRuleItem = NoticeEvidence & {
  key:string; lineId?:string; lineNumber?:number; locator?:string|null; scope?:readonly string[];needsScope:boolean;manual:boolean
}

export function savedNoticeProblem(target: FormContextSource,notice: FormContextSource | undefined) {
  if (notice?.extraction.state!=='available' || !notice.text?.trim()) {
    return target.parent_reference_state==='missing'
      ? '父来源待核对。可继续填写，确认有效通知及提交要求后才能导出。'
      : '请先选择可核对的通知正文，再确认导出。'
  }
  if (target.parent_reference_state==='valid' && target.parent_source_id!==notice.source_id) {
    return '这份附件对应另一份通知，请选择其父来源核对。'
  }
  if (notice.text.length>30_000) return '通知正文超过本机核对范围，请确认有效的精简通知来源。'
  return ''
}

export function recheckSavedForm(latest: FormContext,source: FormContextSource,key: string,noticeId: string,
                                 signature: string,scopes: ScopeSelections,excluded: readonly string[]) {
  const current = latest.sources.find(item=>item.source_id===source.source_id)
  if (!current || savedDraftKey(latest.batch_id,current)!==key) {
    throw Error('这份原件已移除或改版。填写值已保留，请重新读取并核对原件。')
  }
  const currentNotice = latest.sources.find(item=>item.source_id===noticeId)
  const blocked = originalProblem(current) || savedNoticeProblem(current,currentNotice)
  if (blocked) throw Error(blocked)
  const updated = savedRules(latest,currentNotice,current.source_id,scopes,excluded)
  if (current.parent_reference_state!==source.parent_reference_state ||
      current.parent_source_id!==source.parent_source_id || updated.signature!==signature) {
    throw Error('这份表的通知要求或来源已变化。填写值已保留，请重新读取并确认。')
  }
  return current
}
