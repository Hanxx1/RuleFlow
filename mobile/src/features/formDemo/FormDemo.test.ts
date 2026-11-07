import {describe,expect,it} from 'vitest'
import {strFromU8,unzipSync} from 'fflate'
import {avatarUrl,buildForm} from './exportForm'
import {exampleValues,isCompetitionNotice,leaveDays,proposedFilename,reviewForm,scenarios,validateFilename} from './scenarios'

const scholarship = scenarios[0]
const leave = scenarios[1]
const proof = scenarios[2]
const photo = scenarios[3]

describe('offline form review',()=>{
  it('requires all applicant fields across four scenarios',()=>{
    for (const scenario of scenarios) {
      expect(Object.keys(reviewForm(scenario,{},false).errors).length).toBeGreaterThan(0)
      expect(reviewForm(scenario,exampleValues[scenario.id],Boolean(scenario.photo)).errors).toEqual({})
    }
  })

  it('validates award groups, ranking, and reason length',()=>{
    const values = {...exampleValues.scholarship,awardName3:'测试奖',rank:'61',reason:'长'.repeat(201)}
    const {errors} = reviewForm(scholarship,values,false)
    expect(Object.keys(errors)).toEqual(expect.arrayContaining(['awardDate3','awardIssuer3','rank','reason']))
  })

  it('checks dates, period order and parental acknowledgment on the official form',()=>{
    const values = exampleValues.leave
    expect(leaveDays(values)).toBe(3)
    expect(reviewForm(leave,values,false).reminders).toHaveLength(1)
    expect(reviewForm(leave,{...values,end:'2026-11-08'},false).errors.end).toBeTruthy()
    expect(reviewForm(leave,{...values,end:'2026-11-31'},false).errors.end).toBeTruthy()
    expect(reviewForm(leave,{...values,end:values.start,startPeriod:'4',endPeriod:'1'},false).errors.endPeriod).toBeTruthy()
    expect(reviewForm(leave,{...values,parentAware:'否'},false).errors.parentAware).toBeTruthy()
  })

  it('requires a photo and a replacement history selection',()=>{
    expect(Object.keys(reviewForm(photo,{...exampleValues.photo,previousReplacement:''},false).errors)).toEqual(['previousReplacement','photo'])
  })

  it('suggests a safe demonstration name and flags event notices for handoff',()=>{
    expect(proposedFilename(scholarship,exampleValues.scholarship)).toContain('林示例-00001234')
    expect(validateFilename('../申请表')).toBeTruthy()
    expect(validateFilename('COM1')).toBeTruthy()
    expect(validateFilename('演示-请假申请')).toBe('')
    expect(isCompetitionNotice('竞赛作品提交截止时间为下周一')).toBe(true)
    expect(isCompetitionNotice('住宿申请请提交材料')).toBe(false)
  })
})

describe('offline Office exports',()=>{
  it('writes applicant text and numeric values and preserves the code sheet',async()=>{
    const result = buildForm(scholarship,exampleValues.scholarship,'','演示-测试')
    const parts = unzipSync(new Uint8Array(await result.blob.arrayBuffer()))
    const xml = strFromU8(parts['xl/worksheets/sheet1.xml'])
    expect(xml).toMatch(/r="J9"[^>]*>.*?00001234/)
    expect(xml).toMatch(/r="C9"[^>]*>.*?00000020050101000X/)
    expect(xml).toMatch(/r="P9"[^>]*t="n"><v>3<\/v>/)
    expect(xml).toMatch(/<c r="AI9" s="50"\/>/)
    expect(parts['xl/worksheets/sheet2.xml']).toBeDefined()
    expect(result.filename).toBe('演示-测试.xlsx')
  })

  it('writes all three DOCX templates, preserves reserved sections and embeds the photo',async()=>{
    for (const scenario of [leave,proof,photo]) {
      const values = {...exampleValues[scenario.id],name:'合成&用户'}
      const result = buildForm(scenario,values,scenario.photo?avatarUrl:'','测试')
      const parts = unzipSync(new Uint8Array(await result.blob.arrayBuffer()))
      const xml = strFromU8(parts['word/document.xml'])
      expect(xml).toContain('合成&amp;用户')
      expect(xml).not.toContain('{{CW:')
      expect(result.filename).toBe('演示-测试.docx')
      if (scenario.id==='proof') expect(xml).toContain('000000001234567890')
      if (scenario.id==='leave') {
        expect(xml.match(/合成&amp;用户/g)).toHaveLength(4)
        expect(xml).toContain('学院保存')
        expect(xml).toContain('任课老师保存')
      }
      if (scenario.photo) expect(parts['word/media/image1.png'].slice(0,4)).toEqual(Uint8Array.of(137,80,78,71))
    }
  })
})
