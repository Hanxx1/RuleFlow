import {describe,expect,it} from 'vitest'
import {emptyExperience,type Experience} from '../experience/archive'
import {awardCandidates,currentAward,planAward,retainAwardUses} from './accountAwardFill'

const award:Experience = {
  ...emptyExperience(),id:'a',revision:1,confirmed:true,title:'建模优胜奖',month:'2026-04',issuer:'大学教务处',
}

describe('formal award placement',()=>{
  it('limits options to confirmed awards within the template period and field limits',()=>{
    const earlier = {...award,id:'early',month:'2025-11'}
    expect(awardCandidates([award,earlier,{...award,confirmed:false},{...award,kind:'project'},
      {...award,month:'2026-09'},{...award,title:'奖'.repeat(89)},{...award,issuer:''}])).toEqual([earlier,award])
  })

  it('chooses only an empty row and preserves earlier partial and later manual rows',()=>{
    expect(planAward(award,{awardName1:'手工填写',awardDate3:'2026年5月'})?.fields).toEqual({
      awardDate2:'2026年4月',awardName2:award.title,awardIssuer2:award.issuer,
    })
  })

  it('checks chronological order across empty rows and returns no placement if existing rows are out of order',()=>{
    expect(Object.keys(planAward(award,{awardDate2:'2026年5月'})!.fields)).toContain('awardDate1')
    expect(planAward(award,{awardDate1:'2026年5月',awardDate4:'2026年3月'})).toBeUndefined()
    expect(planAward(award,{awardDate1:'2026年4月',awardDate2:'2026年4月',awardDate3:'2026年4月',awardDate4:'2026年4月'})).toBeUndefined()
  })

  it('rejects a duplicate even if the month is entered with a leading zero',()=>{
    expect(planAward(award,{awardDate3:'2026年04月',awardName3:award.title,awardIssuer3:award.issuer})).toBeUndefined()
  })

  it('rejects outdated, deleted and unconfirmed revisions, ignoring changes to other entries',()=>{
    expect(currentAward(award,[award,{...award,id:'b',revision:2}])).toBe(award)
    expect(currentAward(award,[{...award,revision:2}])).toBeUndefined()
    expect(currentAward(award,[])).toBeUndefined()
    expect(currentAward(award,awardCandidates([{...award,confirmed:false}]))).toBeUndefined()
  })

  it('keeps the confirmed source for unchanged values when the user edits just one field',()=>{
    const plan = planAward(award,{})!
    const changed = {...plan.fields,awardName1:'手工修改'}
    expect(retainAwardUses([plan],changed)).toEqual([{...plan,fields:{awardDate1:'2026年4月',awardIssuer1:award.issuer}}])
    expect(retainAwardUses([plan],{})).toEqual([])
    expect(plan.fields.awardName1).toBe(award.title)
  })
})
