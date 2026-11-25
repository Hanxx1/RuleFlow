import {describe,expect,it} from 'vitest'
import {clearFormDrafts,readDraftReference,readFormDrafts,saveFormDraft} from './savedFormDrafts'
import {clearOwnerFormDrafts,savedDraftReturnPath} from './savedDraftSession'
import {scenarios} from './scenarios'

const form = scenarios.find(scenario=>scenario.id==='photo')!
const reference = (batch='batch-a',source='form-a',revision=0) =>
  JSON.stringify([batch,source,'document-a',revision,'a'.repeat(64)])
function storage() {
  const records = new Map<string,string>()
  return {
    get length() { return records.size },
    key: (index:number) => [...records.keys()][index] ?? null,
    getItem: (key:string) => records.get(key) ?? null,
    setItem: (key:string,value:string) => { records.set(key,value) },
    removeItem: (key:string) => { records.delete(key) },
  }
}

describe('tab-scoped saved form drafts',()=>{
  it('restores only approved values and saves no case-specific free text, filenames or authorization',()=>{
    const tab = storage()
    const key = reference()
    saveFormDraft('owner-a','batch-a',key,form,{
      name:'测试姓名',studentId:'00004123',identity:'身份证测试值',phone:'电话号码',
      reason:'本次事由',address:'住址',photo:'测试照片',filename:'自定义文件名',confirm:'true',
    },0,tab)
    expect(readFormDrafts('owner-a','batch-a',tab)).toEqual([
      {key,scenarioId:'photo',revision:1,values:{name:'测试姓名',studentId:'00004123'}},
    ])
    const stored = tab.getItem(tab.key(0)!)!
    for (const omitted of ['本次事由','身份证测试值','电话号码','住址','测试照片','自定义文件名','confirm']) {
      expect(stored).not.toContain(omitted)
    }
  })

  it('isolates owners, batches and different tab stores',()=>{
    const tab = storage()
    saveFormDraft('owner-a','batch-a',reference(),form,{name:'测试姓名'},0,tab)
    expect(readFormDrafts('owner-b','batch-a',tab)).toEqual([])
    expect(readFormDrafts('owner-a','batch-b',tab)).toEqual([])
    expect(readFormDrafts('owner-a','batch-a',storage())).toEqual([])
    expect(()=>saveFormDraft('owner-a','batch-b',reference(),form,{},0,tab)).toThrow('原件版本待核对')
  })

  it('keeps replacement sources and document revisions in separate drafts',()=>{
    const tab = storage()
    const keys = [reference(),reference('batch-a','form-b'),reference('batch-a','form-a',1)]
    keys.forEach((key,index)=>saveFormDraft('owner-a','batch-a',key,form,{name:'测试姓名'+index},0,tab))
    expect(readFormDrafts('owner-a','batch-a',tab).map(item=>[item.key,item.values.name]))
      .toEqual(keys.map((key,index)=>[key,'测试姓名'+index]))
  })

  it('does not overwrite a newer save and lets a deliberate save remove a cleared value',()=>{
    const tab = storage()
    const key = reference()
    saveFormDraft('owner-a','batch-a',key,form,{name:'第一次',studentId:'00004123'},0,tab)
    saveFormDraft('owner-a','batch-a',key,form,{name:'第二次',studentId:''},1,tab)
    expect(()=>saveFormDraft('owner-a','batch-a',key,form,{name:'过期输入'},1,tab)).toThrow('保存版本已变化')
    expect(readFormDrafts('owner-a','batch-a',tab)[0]).toMatchObject({revision:2,values:{name:'第二次'}})
  })

  it('clears only the selected batch or the exiting owner and preserves unrelated storage',()=>{
    const tab = storage()
    tab.setItem('app-setting','keep')
    for (const owner of ['owner-a','owner-b']) {
      for (const batch of ['batch-a','batch-b']) saveFormDraft(owner,batch,reference(batch),form,{name:owner},0,tab)
    }
    clearFormDrafts('owner-a','batch-a',tab)
    expect(readFormDrafts('owner-a','batch-a',tab)).toEqual([])
    expect(readFormDrafts('owner-a','batch-b',tab)).toHaveLength(1)
    clearOwnerFormDrafts('owner-a',tab)
    expect(readFormDrafts('owner-a','batch-b',tab)).toEqual([])
    expect(readFormDrafts('owner-b','batch-a',tab)).toHaveLength(1)
    expect(readFormDrafts('owner-b','batch-b',tab)).toHaveLength(1)
    expect(tab.getItem('app-setting')).toBe('keep')
  })

  it('rejects corrupt records without changing them, and surfaces storage failures',()=>{
    const tab = storage()
    saveFormDraft('owner-a','batch-a',reference(),form,{},0,tab)
    const key = tab.key(0)!
    tab.setItem(key,'{invalid')
    expect(()=>readFormDrafts('owner-a','batch-a',tab)).toThrow('无法读取')
    expect(tab.getItem(key)).toBe('{invalid')
    const blocked = {...storage(),setItem:()=>{throw new Error('quota')}}
    expect(()=>saveFormDraft('owner-a','batch-a',reference(),form,{name:'仍在页面'},0,blocked))
      .toThrow('当前填写内容仍在')
  })

  it('only resumes a validated internal batch path after login',()=>{
    expect(savedDraftReturnPath('a1-b2')).toBe('/imports/a1-b2/forms')
    for (const input of ['',null,['batch-a'],'../cases','//other.example','x'.repeat(129)]) {
      expect(savedDraftReturnPath(input)).toBe('/home')
    }
    expect(readDraftReference(JSON.stringify(['batch','source','doc',-1,'a'.repeat(64)]))).toBeUndefined()
  })
})
