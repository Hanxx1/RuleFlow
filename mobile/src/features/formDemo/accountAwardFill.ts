import {experienceSource,type Experience} from '../experience/archive'
import {awardSlots,readAward} from './demoAwards'
import {scholarshipAwardCutoff,type FormValues} from './scenarios'

export type AwardSlot = (typeof awardSlots)[number]
export type AwardUse = {
  entry:Pick<Experience,'id'|'revision'|'title'>
  source:ReturnType<typeof experienceSource>
  fields:FormValues
}
const monthNumber = (date:string) => {
  const month = /^(\d{4})年(0?[1-9]|1[0-2])月$/.exec(date.trim())
  return month ? 100*Number(month[1])+Number(month[2]) : 0
}
const fieldsAt = (slot:AwardSlot,date:string,name:string,issuer:string): FormValues =>
  ({['awardDate'+slot]:date,['awardName'+slot]:name,['awardIssuer'+slot]:issuer})

export function awardCandidates(entries:Experience[]) {
  return entries.filter(entry=>{
    if (!entry.confirmed || entry.kind!=='award') return false
    const [year,month] = entry.month.split('-')
    const date = `${year}年${Number(month)}月`
    const numericMonth = monthNumber(date)
    return Boolean(numericMonth && numericMonth<=scholarshipAwardCutoff &&
      readAward(fieldsAt(1,date,entry.title,entry.issuer),1))
  }).sort((a,b)=>a.month.localeCompare(b.month))
}

export function planAward(entry:Experience,current:FormValues): AwardUse | undefined {
  const [year,month] = entry.month.split('-')
  const date = `${year}年${Number(month)}月`
  const when = monthNumber(date)
  const duplicate = awardSlots.some(slot=>{
    const row = readAward(current,slot)
    return row && monthNumber(row.date)===when && row.name===entry.title && row.issuer===entry.issuer
  })
  if (duplicate) return
  const slot = awardSlots.find(position=>{
    if (Object.keys(fieldsAt(position,'','','')).some(id=>current[id]?.trim())) return false
    return awardSlots.every(other=>{
      const typed = monthNumber(current['awardDate'+other] || '')
      return !typed || (other<position ? typed<=when : typed>=when)
    })
  })
  if (slot) return {
    entry:{id:entry.id,revision:entry.revision,title:entry.title},
    source:experienceSource(entry),fields:fieldsAt(slot,date,entry.title,entry.issuer),
  }
}

export function currentAward(entry:Pick<Experience,'id'|'revision'>,candidates:Experience[]) {
  return candidates.find(item=>item.id===entry.id && item.revision===entry.revision)
}

export function retainAwardUses(uses:AwardUse[],values:FormValues) {
  return uses.flatMap(use=>{
    const fields = Object.fromEntries(Object.entries(use.fields).filter(([id,value])=>values[id]===value))
    return Object.keys(fields).length ? [{...use,fields}] : []
  })
}
