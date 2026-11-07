import {describe,expect,it} from 'vitest'
import {strFromU8,unzipSync} from 'fflate'
import {buildForm} from './exportForm'
import {profileKey,resolveDemoProfile} from './demoProfile'
import {exampleValues,isCompetitionNotice,leaveDays,proposedFilename,reviewForm,scenarioFields,scenarios,validateFilename} from './scenarios'

const find = (id: string) => scenarios.find(scenario=>scenario.id===id)!
const scholarship = find('scholarship')
const leave = find('leave')

describe('offline form review',()=>{
  it('generates required fields for all eleven real templates and accepts complete inputs',()=>{
    expect(new Set(scenarios.map(scenario=>scenario.id)).size).toBe(11)
    for (const scenario of scenarios) {
      expect(Object.keys(reviewForm(scenario,{},false).errors)).toContain('name')
      expect(reviewForm(scenario,exampleValues[scenario.id],false).errors,scenario.id).toEqual({})
    }
  })

  it('validates award groups, ranking and reason length',()=>{
    const values = {...exampleValues.scholarship,awardName3:'测试奖',rank:'61',reason:'长'.repeat(201)}
    expect(Object.keys(reviewForm(scholarship,values,false).errors)).toEqual(
      expect.arrayContaining(['awardDate3','awardIssuer3','rank','reason']),
    )
  })

  it('validates dates, period order and acknowledgment',()=>{
    const values = exampleValues.leave
    expect(leaveDays(values)).toBe(3)
    expect(reviewForm(leave,values,false).reminders).toHaveLength(1)
    expect(reviewForm(leave,{...values,end:'2026-11-08'},false).errors.end).toBeTruthy()
    expect(reviewForm(leave,{...values,end:'2026-11-31'},false).errors.end).toBeTruthy()
    expect(reviewForm(leave,{...values,end:values.start,startPeriod:'4',endPeriod:'1'},false).errors.endPeriod).toBeTruthy()
    expect(reviewForm(leave,{...values,parentAware:'否'},false).errors.parentAware).toBeTruthy()
  })

  it('preserves identity scope and reads only fields approved for reuse',()=>{
    const profile = {revision:1,values:{name:'林同学','ncwu:studentId':'00001234',identity:'保留在当前表'},awards:[]}
    expect(resolveDemoProfile(find('stay'),profile)).toEqual({name:'林同学',studentId:'00001234'})
    expect(resolveDemoProfile(find('resume'),profile)).toEqual({name:'林同学',studentId:'00001234'})
    expect(resolveDemoProfile(scholarship,profile)).toEqual({name:'林同学'})
    expect(profileKey(scholarship,scenarioFields(scholarship).find(field=>field.id==='identity')!)).toBeUndefined()
  })

  it('routes event notices and validates filenames',()=>{
    expect(proposedFilename(scholarship,exampleValues.scholarship)).toContain('林示例-00001234')
    expect(validateFilename('../申请表')).toBeTruthy()
    expect(validateFilename('COM1')).toBeTruthy()
    expect(validateFilename('演示-请假申请')).toBe('')
    expect(isCompetitionNotice('竞赛作品提交截止时间为下周一')).toBe(true)
    expect(isCompetitionNotice('住宿申请请提交材料')).toBe(false)
  })
})

describe('offline Office exports',()=>{
  it('writes exact applicant values and preserves the XLSX code sheet',async()=>{
    const result = buildForm(scholarship,exampleValues.scholarship,'','演示-测试')
    const parts = unzipSync(new Uint8Array(await result.blob.arrayBuffer()))
    const xml = strFromU8(parts['xl/worksheets/sheet1.xml'])
    expect(xml).toMatch(/r="J9"[^>]*>.*?00001234/)
    expect(xml).toMatch(/r="C9"[^>]*>.*?00000020050101000X/)
    expect(xml).toMatch(/r="P9"[^>]*t="n"><v>3<\/v>/)
    expect(xml).toMatch(/<c r="AI9" s="50"\/>/)
    expect(parts['xl/worksheets/sheet2.xml']).toBeDefined()
  })

  it.each(scenarios.filter(scenario=>scenario.format==='docx'))('fills $id without residual applicant markers',async scenario=>{
    const values = {...exampleValues[scenario.id],name:'合成&用户'}
    const result = buildForm(scenario,values,'','测试')
    const parts = unzipSync(new Uint8Array(await result.blob.arrayBuffer()))
    const xml = strFromU8(parts['word/document.xml'])
    expect(xml).toContain('合成&amp;用户')
    expect(xml).not.toContain('{{CW:')
    expect(result.filename).toBe('演示-测试.docx')
    if (scenario.id==='leave') expect(xml.match(/合成&amp;用户/g)).toHaveLength(4)
    if (scenario.id==='proof') expect(xml).toContain('000000001234567890')
    if (scenario.id==='defer') expect(xml.match(/合成&amp;用户/g)).toHaveLength(3)
    if (scenario.id==='resume') {
      expect(xml).not.toContain('如页面不够')
      expect(xml.replace(/<[^>]+>/g,'')).toContain('此栏由学院填写')
    }
    if (scenario.id==='workstudy') {
      expect(xml).not.toContain('XXXXXXXXXXXXXXXX')
      expect(xml).toContain(exampleValues[scenario.id].achievement)
      expect(xml).toContain('请勿调整本页表格大小')
    }
    if (scenario.photo==='physical') {
      expect(xml).not.toContain('<w:drawing')
      expect(Object.keys(parts).filter(path=>path.startsWith('word/media/'))).toHaveLength(0)
    }
  })
})
