import type {FormValues} from './scenarios'

export type DemoAward = {date: string; name: string; issuer: string}
export const awardSlots = [1,2,3,4] as const

export function readAward(values: FormValues, slot: number): DemoAward | undefined {
  const date = values['awardDate'+slot]?.trim()
  const name = values['awardName'+slot]?.trim()
  const issuer = values['awardIssuer'+slot]?.trim()
  if (!date || !/^\d{4}年(?:0?[1-9]|1[0-2])月$/.test(date) || !name || !issuer ||
      [...name].length > 88 || [...issuer].length > 88) return undefined
  return {date,name,issuer}
}

export function nextAwardSlot(values: FormValues) {
  return awardSlots.find(slot=>['awardDate','awardName','awardIssuer'].every(key=>!values[key+slot]?.trim()))
}

export function writeAward(values: FormValues, award: DemoAward) {
  const slot = nextAwardSlot(values)
  if (!slot) return undefined
  return {...values,['awardDate'+slot]:award.date,['awardName'+slot]:award.name,['awardIssuer'+slot]:award.issuer}
}

export function awardReason(awards: DemoAward[]) {
  const names = awards.map(award=>award.name).join('、')
  const details = names && [...names].length <= 65 ? '本次申请附上已选获奖经历：'+names+'。' : ''
  return '本人希望以本次申请为契机，回顾学习过程中的收获和不足。'+details+
    '在接下来的学习中，我会合理安排时间，主动向老师和同学请教，持续完善学习方法。'+
    '我也愿意参加与专业相关的实践和集体活动，把课程所学用于解决具体问题，并定期总结改进情况。'+
    '我将按申请要求提交相关材料，便于学校核实。'
}
