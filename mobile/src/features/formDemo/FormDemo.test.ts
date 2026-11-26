import {describe,expect,it} from 'vitest'
import {strFromU8,strToU8,unzipSync,zipSync} from 'fflate'
import templateData from './templateData.json'
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

  it('bounds a same-day total and leaves a cross-day total for timetable confirmation',()=>{
    const values = {...exampleValues.leave,start:'2026-11-10',end:'2026-11-10',startPeriod:'2',endPeriod:'4'}
    expect(reviewForm(leave,{...values,periodCount:'4'},false).errors.periodCount).toContain('起止节次')
    expect(reviewForm(leave,{...values,periodCount:'2'},false).errors.periodCount).toBeUndefined()
    expect(reviewForm(leave,{...values,end:'2026-11-11',endPeriod:'1',periodCount:'4'},false).errors).toEqual({})
    expect(reviewForm(leave,{...values,reason:'（具体事由）家中有事'},false).errors.reason).toContain('替换')
    expect(reviewForm(leave,{...values,reason:'由于家中有事。'},false).errors.reason).toContain('原因短语')
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
  it.each(['林同学','林知遥'])('fills both leave copies without repeating the address suffix for %s',async name=>{
    const reason = '临时陪同家人就医'
    const result = buildForm(leave,{...exampleValues.leave,name,reason},'','请假')
    const parts = unzipSync(new Uint8Array(await result.blob.arrayBuffer()))
    const text = strFromU8(parts['word/document.xml']).replace(/<[^>]+>/g,'')
    const addressed = name.endsWith('同学') ? name : name+'同学'
    expect(text.split('班的'+addressed+'，由于'+reason+'，不能')).toHaveLength(3)
    expect(text.split('请假人： '+name)).toHaveLength(3)
    expect(text).not.toContain('同学同学')
    expect(text).not.toContain('（具体事由）')
    expect(text).toContain('任课老师批准签名')
  })

  it('rejects a prepared leave template missing one of the two copy positions',()=>{
    const asset = 'leave.docx'
    const original = templateData[asset]
    const parts = unzipSync(Uint8Array.from(atob(original),letter=>letter.charCodeAt(0)))
    const part = 'word/document.xml'
    const xml = strFromU8(parts[part])
    expect(xml.match(/\{\{CW:course\}\}/g)).toHaveLength(2)
    parts[part] = strToU8(xml.replace('{{CW:course}}',''))
    templateData[asset] = Buffer.from(zipSync(parts)).toString('base64')
    try {
      expect(()=>buildForm(leave,exampleValues.leave,'','请假')).toThrow('请假表两联的填写位置不一致')
    } finally {
      templateData[asset] = original
    }
  })

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
