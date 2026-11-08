import {describe,expect,it} from 'vitest'
import templateData from './templateData.json'
import {analyzeNotice,applyNotice,matchAttachment,noticeFilename,readNotice,suggestedTarget} from './noticeIntake'
import {exampleValues,reviewForm,scenarios} from './scenarios'
import {buildForm} from './exportForm'

const scholarship = scenarios.find(scenario=>scenario.id==='scholarship')!
const resume = scenarios.find(scenario=>scenario.id==='resume')!

describe('notice-driven form intake',()=>{
  it('matches source bytes and rejects a same-name modified workbook',async()=>{
    const original = Uint8Array.from(atob(templateData['scholarship.xlsx']),char=>char.charCodeAt(0))
    expect((await matchAttachment(new File([original],'重命名.xlsx'))).scenario?.id).toBe('scholarship')
    original[10] ^= 1
    expect((await matchAttachment(new File([original],'重命名.xlsx'))).scenario).toBeUndefined()
    expect((await matchAttachment(new File(['not an Office package'],'假.xlsx'))).error).toBeTruthy()
  })

  it('uses source line references to constrain text and compute the official file name',async()=>{
    const text = '复学申请\n申请理由 12–30 字。\n申请表文件命名为“学号-姓名-复学申请.docx”。\n申请人签字后交件。'
    expect(await readNotice(new File([text],'通知.txt'))).toBe(text)
    const requirements = analyzeNotice(text)
    const applied = applyNotice(resume,requirements)
    expect(applied.conflict).toBe('')
    expect(requirements.evidence.map(item=>[item.line,item.kind])).toEqual([[2,'length'],[3,'filename'],[4,'review']])
    const values = exampleValues.resume
    expect(reviewForm(applied.scenario,{...values,reason:'复学'},false).errors.reason).toContain('12')
    const filename = noticeFilename(requirements,values)
    expect(filename).toBe('00001234-林示例-复学申请')
    expect(buildForm(applied.scenario,values,'',filename,false).filename).toBe(filename+'.docx')
  })

  it('keeps attachment naming and uncertain requirements for review',()=>{
    const requirements = analyzeNotice('邮件主题命名为“学号+姓名”。\n提交扫描件。\n竞赛报名材料截止周一。')
    expect(requirements.naming).toBeUndefined()
    expect(requirements.competition).toBe(true)
    expect(requirements.evidence.every(item=>item.kind==='review')).toBe(true)
  })

  it('stops conflicting word limits, formats and unverified photo positions',()=>{
    expect(applyNotice(scholarship,analyzeNotice('申请理由不超过 50 字。')).conflict).toBeTruthy()
    expect(applyNotice(resume,analyzeNotice('申请表文件命名为“学号-姓名-复学申请.xlsx”。')).conflict).toBeTruthy()
    expect(applyNotice(resume,analyzeNotice('打印后粘贴照片。')).conflict).toContain('没有已核验的照片位置')
  })

  it('accepts bounded underscore names and keeps fonts and email actions for review',()=>{
    const requirements = analyzeNotice('复学申请表文件命名格式：学号_姓名_复学申请.docx。\n申请理由使用宋体小四。\n邮件主题命名为“学号_姓名”。')
    expect(noticeFilename(requirements,exampleValues.resume)).toBe('00001234_林示例_复学申请')
    expect(requirements.evidence.map(item=>[item.line,item.kind])).toEqual([[1,'filename'],[2,'review'],[3,'review']])
    expect(analyzeNotice('文件名：学号_姓名_无法确认的说明').naming).toBeUndefined()
    expect(analyzeNotice('文件名为“学院_姓名-表格.docx”').naming).toBeUndefined()
  })

  it('keeps rule scope on the referenced original and leaves unspecified scope open',()=>{
    const text = '附件10文件名为“学号-姓名-复学申请.xlsx”。\n复学申请理由至少 20 字。\n申请理由最多 50 字。'
    const evidence = analyzeNotice(text).evidence
    const targets = [
      {id:1,name:'附件1_复学申请.docx',title:'复学申请'},
      {id:2,name:'附件10_其他登记.docx',title:'其他登记'},
    ]
    expect(evidence.map(item=>suggestedTarget(item,targets))).toEqual([2,1,undefined])
    const forResume = analyzeNotice(text,clause=>clause.id===evidence[1].id)
    expect(forResume.naming).toBeUndefined()
    expect(forResume.evidence[0].line).toBe(2)
    expect(applyNotice(resume,forResume).conflict).toBe('')
    expect(suggestedTarget(evidence[0],targets.slice(0,1))).toBeUndefined()
  })

  it('routes competition actions with evidence and leaves scholarship awards in the form flow',()=>{
    const competition = analyzeNotice('学校工作安排\n竞赛作品提交截止时间为下周一。')
    expect(competition.competitionEvidence).toEqual({line:2,text:'竞赛作品提交截止时间为下周一。'})
    expect(analyzeNotice('奖学金评选通知\n提交表格前请填写学科竞赛获奖经历。').competition).toBe(false)
  })
})
