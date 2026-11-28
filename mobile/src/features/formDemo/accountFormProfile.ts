import {resolvedFacts,type Workspace} from '../../services/clientWorkspace'
import {scenarioFields,type FormValues,type Scenario} from './scenarios'

// Only templates for the applicant's current enrollment use a confirmed school.
const applicantSchools: Record<string,string> = {
  scholarship:'南京审计大学',leave:'广东财经大学',stay:'华北水利水电大学',
  defer:'广东工业大学',workstudy:'南开大学',major:'开封职业学院',
  review:'四川建筑职业技术大学',exemption:'四川建筑职业技术大学',
}
const mappedFields = new Map([
  ['college','college'],['major','major'],['className','class_name'],['studentType','student_type'],
])
const schoolName = (value:string) => value.normalize('NFKC').replace(/\s+/g,'')

export type ProfileCandidate = {
  id:string;label:string;value:string;refs:{id:string;quote:string;validUntil:string|null}[]
}

export function reviewAccountProfile(workspace: Workspace,scenario: Scenario,caseId: string,
                                     current: FormValues,today?: string) {
  const candidates: ProfileCandidate[] = []
  const skipped: string[] = []
  const resolved = resolvedFacts(workspace,caseId,today)
  const {facts,evidence,conflicts} = resolved
  const school = applicantSchools[scenario.id]
  let issue = ''
  if (!school) issue = '此模板暂无可从当前学籍画像带入的字段。'
  else if (conflicts.includes('school')) issue = '画像学校存在冲突，请先在个人画像中核对。'
  else if (typeof facts.school!=='string') issue = '画像缺少可用学校，请先确认适用于本次的学校全称。'
  else if (schoolName(facts.school)!==school) issue = '画像学校与此原表适用的学校不同，仍可手工填写。'
  if (issue) return {revision:workspace.revision,candidates,skipped,issue}

  for (const field of scenarioFields(scenario)) {
    const key = mappedFields.get(field.id)
    if (!key || field.sensitive || field.export===false || current[field.id]?.trim()) continue
    const fact = facts[key]
    const text = key==='student_type' ? (fact==='undergraduate' ? '本科' : '') : typeof fact==='string' ? fact.trim() : ''
    if (!text || (field.choices && !field.choices.includes(text)) || (field.max!==undefined && text.length>field.max)) {
      skipped.push(field.label)
      continue
    }
    const refs = [...(evidence[key] || []),...(evidence.school || [])]
      .map(({id,quote,validUntil})=>({id,quote,validUntil}))
    if (refs.length) candidates.push({id:field.id,label:field.label,value:text,refs})
  }
  return {revision:workspace.revision,candidates,skipped,issue}
}

export function applyProfileCandidates(current: FormValues,candidates: ProfileCandidate[],selected: readonly string[]) {
  return candidates.filter(item=>selected.includes(item.id) && !current[item.id]?.trim())
}

export function staleProfileLabels(applied: ProfileCandidate[],available: ProfileCandidate[]) {
  return applied.filter(use=>!available.some(item=>item.id===use.id && item.value===use.value &&
    JSON.stringify(item.refs)===JSON.stringify(use.refs))).map(item=>item.label)
}
