import type {AwardUse} from './accountAwardFill'
import {scenarioFields,type Scenario} from './scenarios'

const purposes: Record<string,string> = {
  leave:'现申请上述时段请假',proof:'现申请办理学历及学位证明',photo:'现申请补发学生证',
  stay:'现申请在上述时段留校住宿',defer:'现申请该课程缓考',resume:'现申请复学',
  major:'现申请转入所填专业',review:'现申请核查该课程成绩',exemption:'现申请免修该课程',
}

export type ReasonAward = Pick<AwardUse,'entry'|'source'>
export type ReasonVersion = {text:string;awards:ReasonAward[]}

export function reasonField(scenario:Scenario) {
  if (scenario.id!=='scholarship' && !purposes[scenario.id]) return
  return scenarioFields(scenario).find(item=>item.id==='reason' && item.type==='long' && item.export!==false)
}

export function reasonAwards(uses:AwardUse[]):ReasonAward[] {
  return uses.filter(use=>Object.keys(use.fields).length===3).map(({entry,source})=>({entry,source}))
}

export const reasonLength = (text:string) => [...text.trim()].length

export function draftApplicationReason(scenario:Scenario,details:string,awards:ReasonAward[]) {
  const field = reasonField(scenario)
  if (!field) return {issue:'此表请手工填写理由。'}
  const withinLimits = (text:string) => {
    const length = reasonLength(text)
    return length >= (field.min ?? 1) && length <= (field.max ?? Infinity)
  }
  if (scenario.id!=='scholarship') {
    const basis = details.trim()
    if (!basis) return {issue:'请先写明真实事由。'}
    const full = basis+(/[。！？.!?；;]$/.test(basis)?'':'。')+purposes[scenario.id]+'。'
    const text = [full,basis].find(withinLimits)
    return text ? {version:{text,awards:[]}} : {issue:'文字不符合本表字数要求，请调整事由后重试，或直接手写。'}
  }
  const selected = [...new Map(awards.map(item=>[item.entry.id,item])).values()]
  const awardText = selected.length ? '获奖情况包括'+selected.map(item=>'「'+item.entry.title+'」').join('、')+'。' : ''
  const phrases = [
    '希望以此次申请为契机，认真梳理本学年的情况，明确下一阶段的学习目标和改进方向。',
    '今后我会按阶段检查学习进展，及时调整学习安排，并主动参与与专业相关的实践。',
    '恳请老师结合本次申请材料审阅。',
  ]
  for (const opening of ['本人申请国家奖学金。','申请国家奖学金。']) {
    let text = opening+awardText
    for (const sentence of phrases) {
      if (reasonLength(text+sentence) <= (field.max ?? Infinity)) text += sentence
      if (withinLimits(text)) return {version:{text,awards:selected}}
    }
  }
  return {issue:'按本表字数要求无法生成完整稿。请减少所选奖项或手工填写。'}
}
