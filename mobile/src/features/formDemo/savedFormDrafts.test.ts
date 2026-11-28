import {describe,expect,it} from 'vitest'
import {clearFormDrafts,DraftRevisionConflict,readDraftReference,readFormDrafts,saveFormDraft} from './savedFormDrafts'
import type {ReasonVersion} from './reasonDraft'
import {clearOwnerFormDrafts,savedDraftReturnPath} from './savedDraftSession'
import {scenarios} from './scenarios'

const form = scenarios.find(scenario=>scenario.id==='photo')!
const scholarship = scenarios.find(scenario=>scenario.id==='scholarship')!
const accepted:ReasonVersion = {
  text:'已采用的草稿',
  awards:[{entry:{id:'award-a',title:'建模优胜奖',revision:2},
    source:{id:'block:client:award-a',revision:2,quote:'2026-04 · 建模优胜奖 · 教务处'}}],
}
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
    },0,{storage:tab})
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
    saveFormDraft('owner-a','batch-a',reference(),form,{name:'测试姓名'},0,{storage:tab})
    expect(readFormDrafts('owner-b','batch-a',tab)).toEqual([])
    expect(readFormDrafts('owner-a','batch-b',tab)).toEqual([])
    expect(readFormDrafts('owner-a','batch-a',storage())).toEqual([])
    expect(()=>saveFormDraft('owner-a','batch-b',reference(),form,{},0,{storage:tab})).toThrow('原件版本待核对')
  })

  it('keeps replacement sources and document revisions in separate drafts',()=>{
    const tab = storage()
    const keys = [reference(),reference('batch-a','form-b'),reference('batch-a','form-a',1)]
    keys.forEach((key,index)=>saveFormDraft('owner-a','batch-a',key,form,{name:'测试姓名'+index},0,{storage:tab}))
    expect(readFormDrafts('owner-a','batch-a',tab).map(item=>[item.key,item.values.name]))
      .toEqual(keys.map((key,index)=>[key,'测试姓名'+index]))
  })

  it('does not overwrite a newer save and lets a deliberate save remove a cleared value',()=>{
    const tab = storage()
    const key = reference()
    saveFormDraft('owner-a','batch-a',key,form,{name:'第一次',studentId:'00004123'},0,{storage:tab})
    saveFormDraft('owner-a','batch-a',key,form,{name:'第二次',studentId:''},1,{storage:tab})
    expect(()=>saveFormDraft('owner-a','batch-a',key,form,{name:'过期输入'},1,{storage:tab})).toThrow(DraftRevisionConflict)
    expect(readFormDrafts('owner-a','batch-a',tab)[0]).toMatchObject({revision:2,values:{name:'第二次'}})
  })

  it('clears only the selected batch or the exiting owner and preserves unrelated storage',()=>{
    const tab = storage()
    tab.setItem('app-setting','keep')
    for (const owner of ['owner-a','owner-b']) {
      for (const batch of ['batch-a','batch-b']) saveFormDraft(owner,batch,reference(batch),form,{name:owner},0,{storage:tab})
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
    saveFormDraft('owner-a','batch-a',reference(),form,{},0,{storage:tab})
    const key = tab.key(0)!
    tab.setItem(key,'{invalid')
    expect(()=>readFormDrafts('owner-a','batch-a',tab)).toThrow('无法读取')
    expect(tab.getItem(key)).toBe('{invalid')
    const blocked = {...storage(),setItem:()=>{throw new Error('quota')}}
    expect(()=>saveFormDraft('owner-a','batch-a',reference(),form,{name:'仍在页面'},0,{storage:blocked}))
      .toThrow('当前填写内容仍在')
  })

  it('only resumes a validated internal batch path after login',()=>{
    expect(savedDraftReturnPath('a1-b2')).toBe('/imports/a1-b2/forms')
    for (const input of ['',null,['batch-a'],'../cases','//other.example','x'.repeat(129)]) {
      expect(savedDraftReturnPath(input)).toBe('/home')
    }
    expect(readDraftReference(JSON.stringify(['batch','source','doc',-1,'a'.repeat(64)]))).toBeUndefined()
  })

  it('round-trips an opted-in edited reason and only its approved source snapshot',()=>{
    const tab = storage()
    const key = reference()
    const reason = {value:'用户最后写的版本\n次行',accepted,photo:'不保存',confirmed:true}
    const options = {storage:tab,reason}
    saveFormDraft('owner-a','batch-a',key,scholarship,{name:'手填姓名',identity:'不保存'},0,options)
    expect(readFormDrafts('owner-a','batch-a',tab)).toEqual([{
      key,scenarioId:'scholarship',revision:1,values:{name:'手填姓名'},
      reason:{value:reason.value,accepted},
    }])
    expect(tab.getItem(tab.key(0)!)!).not.toContain('不保存')
  })

  it('allows saving a draft that needs more editing and removes a previously opted-in reason when omitted',()=>{
    const tab = storage()
    const key = reference()
    const reason = {value:'字'.repeat(101)}
    saveFormDraft('owner-a','batch-a',key,form,{},0,{storage:tab,reason})
    expect(readFormDrafts('owner-a','batch-a',tab)[0].reason).toEqual(reason)
    saveFormDraft('owner-a','batch-a',key,form,{},1,{storage:tab})
    expect(readFormDrafts('owner-a','batch-a',tab)[0]).not.toHaveProperty('reason')
  })

  it('rejects excessive text and invalid award sources without overwriting the last good record',()=>{
    const tab = storage()
    const key = reference()
    saveFormDraft('owner-a','batch-a',key,scholarship,{name:'上一版'},0,{storage:tab})
    const invalid = {...accepted,awards:[{...accepted.awards[0],source:{...accepted.awards[0].source,revision:99}}]}
    expect(()=>saveFormDraft('owner-a','batch-a',key,scholarship,{},1,{storage:tab,reason:{value:'待核对',accepted:invalid}}))
      .toThrow('理由依据无法核对')
    expect(()=>saveFormDraft('owner-a','batch-a',key,scholarship,{},1,{storage:tab,reason:{value:'字'.repeat(4001)}}))
      .toThrow('无法保存')
    expect(readFormDrafts('owner-a','batch-a',tab)[0].values).toEqual({name:'上一版'})
  })

  it('rejects duplicate provenance and award-derived text on incompatible templates',()=>{
    const tab = storage()
    const reason = {value:'理由',accepted}
    expect(()=>saveFormDraft('owner-a','batch-a',reference(),form,{},0,{storage:tab,reason}))
      .toThrow('理由依据无法核对')
    const duplicate = {value:'理由',accepted:{...accepted,awards:[...accepted.awards,...accepted.awards]}}
    expect(()=>saveFormDraft('owner-a','batch-a',reference(),scholarship,{},0,{storage:tab,reason:duplicate}))
      .toThrow('理由依据无法核对')
  })
})
