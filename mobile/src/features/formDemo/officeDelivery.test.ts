import {describe,expect,it,vi} from 'vitest'
import {strToU8,zipSync} from 'fflate'
import {buildForm} from './exportForm'
import {createOfficeDelivery,officeFilename,officeMime} from './officeDelivery'
import {exampleValues,scenarios} from './scenarios'

const packageBlob = (parts:Record<string,string>,mime=officeMime('docx')) =>
  new Blob([zipSync(Object.fromEntries(Object.entries(parts).map(([name,text])=>[name,strToU8(text)]))).slice().buffer],{type:mime})

describe('verified Office delivery',()=>{
  it('validates valid exports for every known form without renaming the requested output',async()=>{
    for (const scenario of scenarios) {
      const stem = '填好的申请表'
      const filename = officeFilename(scenario.format,stem,true)
      const prepare = createOfficeDelivery(scenario.format,filename,
        ()=>buildForm(scenario,exampleValues[scenario.id],'',stem))
      const result = await prepare()
      expect(result.filename,scenario.id).toBe(filename)
      expect(result.blob.type,scenario.id).toBe(officeMime(scenario.format))
      expect(result.blob.size).toBeGreaterThan(0)
    }
  })

  it('reuses exactly the same verified artifact for later or concurrent requests',async()=>{
    const scenario = scenarios.find(item=>item.id==='leave')!
    const build = vi.fn(()=>buildForm(scenario,exampleValues.leave,'','请假',false))
    const prepare = createOfficeDelivery('docx','请假.docx',build)
    const [first,other] = await Promise.all([prepare(),prepare()])
    expect(other).toBe(first)
    expect(await prepare()).toBe(first)
    expect(build).toHaveBeenCalledTimes(1)
    expect(await createOfficeDelivery('docx','请假.docx',build)()).not.toBe(first)
    expect(build).toHaveBeenCalledTimes(2)
  })

  it('checks the target filename, MIME and empty output before accepting bytes',async()=>{
    const scenario = scenarios.find(item=>item.id==='leave')!
    const good = buildForm(scenario,exampleValues.leave,'','请假',false)
    const badOutputs = [
      {...good,filename:'别名.docx'},
      {...good,blob:new Blob([good.blob],{type:officeMime('xlsx')})},
      {...good,blob:new Blob([],{type:officeMime('docx')})},
    ]
    for (const output of badOutputs) {
      await expect(createOfficeDelivery('docx','请假.docx',()=>output)()).rejects.toThrow('文件名或文件类型')
    }
  })

  it('rejects malformed Office packages and allows retry after a transient build or verification failure',async()=>{
    const scenario = scenarios.find(item=>item.id==='leave')!
    const good = buildForm(scenario,exampleValues.leave,'','请假',false)
    const build = vi.fn()
      .mockImplementationOnce(()=>{throw Error('write failed')})
      .mockReturnValueOnce({...good,blob:packageBlob({'word/document.xml':'<document/>'})})
      .mockReturnValue(good)
    const prepare = createOfficeDelivery('docx',good.filename,build)
    await expect(prepare()).rejects.toThrow('write failed')
    await expect(prepare()).rejects.toThrow('Office 文件校验失败')
    await expect(prepare()).resolves.toMatchObject(good)
    expect(build).toHaveBeenCalledTimes(3)
  })
})
