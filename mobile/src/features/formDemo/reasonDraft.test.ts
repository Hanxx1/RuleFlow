import {describe,expect,it} from 'vitest'
import {applyNotice,type NoticeRequirements} from './noticeIntake'
import {draftApplicationReason,reasonAwards,reasonField,reasonLength,type ReasonAward} from './reasonDraft'
import {scenarios,type Scenario} from './scenarios'

const [scholarship,leave] = scenarios
const award:ReasonAward = {
  entry:{id:'a',revision:2,title:'校园数据应用评比优胜奖'},
  source:{id:'block:client:a',revision:2,quote:'2026-04 · 校园数据应用评比优胜奖 · 校学生创新实践中心'},
}
const withLength = (scenario:Scenario,min:number|undefined,max:number) => {
  const req:NoticeRequirements = {evidence:[],lengths:{reason:{min,max}},physicalPhoto:false,competition:false,conflict:''}
  return applyNotice(scenario,req).scenario
}

describe('application reason drafts',()=>{
  it('generates a scholarship draft without claiming any unprovided awards, numbers or achievements',()=>{
    const result = draftApplicationReason(scholarship,'',[])
    expect(result.version?.awards).toEqual([])
    expect(reasonLength(result.version!.text)).toBeGreaterThanOrEqual(100)
    expect(reasonLength(result.version!.text)).toBeLessThanOrEqual(200)
    expect(result.version?.text).not.toMatch(/获奖|成绩|排名|\d+小时|获得/)
  })

  it('quotes only chosen, confirmed title data and carries each original source once',()=>{
    const result = draftApplicationReason(scholarship,'',[award,award])
    expect(result.version?.text.match(/校园数据应用评比优胜奖/g)).toHaveLength(1)
    expect(result.version?.awards).toEqual([award])
    expect(result.version?.text).not.toContain('校学生创新实践中心')
  })

  it('has no result within conflicting or excessively tight notice limits',()=>{
    expect(draftApplicationReason(withLength(scholarship,150,140),'',[]).issue).toContain('字数')
    const long = {...award,entry:{...award.entry,title:'奖'.repeat(84)}}
    expect(reasonLength(draftApplicationReason(withLength(scholarship,undefined,101),'',[long]).version!.text)).toBe(101)
    expect(draftApplicationReason(withLength(scholarship,undefined,100),'',[long]).issue).toContain('减少')
  })

  it('requires the real event for leave forms and preserves it under the bound notice',()=>{
    expect(draftApplicationReason(leave,'\n ',[]).issue).toContain('真实事由')
    const context = '需到户籍窗口办理手续'
    const full = draftApplicationReason(leave,context,[award]).version
    expect(full).toEqual({text:context+'。现申请上述时段请假。',awards:[]})
    expect(draftApplicationReason(withLength(leave,undefined,reasonLength(context)),context,[]).version?.text).toBe(context)
    expect(draftApplicationReason(withLength(leave,undefined,3),context,[]).issue).toContain('字数')
  })

  it('supports explicit purpose fields only and leaves summary and unknown formats manual',()=>{
    const photo = scenarios.find(item=>item.id==='photo')!
    expect(draftApplicationReason(photo,'原学生证遗失',[]).version?.text).toContain('补发学生证')
    expect(reasonField({...scholarship,id:'other'})).toBeUndefined()
    expect(reasonField(scenarios.find(item=>item.id==='workstudy')!)).toBeUndefined()
    expect(reasonLength(' 甲\n𠮷。 ')).toBe(3)
  })

  it('offers facts only when a whole award row was sourced from the confirmed archive',()=>{
    expect(reasonAwards([
      {...award,fields:{awardName1:award.entry.title}},
      {...award,fields:{awardName2:award.entry.title,awardDate2:'2026年4月',awardIssuer2:'创新实践中心'}},
    ])).toEqual([award])
  })
})
