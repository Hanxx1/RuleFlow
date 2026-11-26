import {describe,expect,it} from 'vitest'
import {applyDraftOperation,DraftRevisionConflict,DraftSessionExpired,draftRetentionMs,
  readDraftReference,recoverableFields,type DraftOperation,type DraftState} from './savedFormDrafts'
import {clearOwnerFormDrafts,savedDraftReturnPath} from './savedDraftSession'
import {scenarios,type FormValues} from './scenarios'

const form = scenarios.find(scenario=>scenario.id==='photo')!
const reference = (batch='batch-a',source='form-a',revision=0,hash='a') =>
  JSON.stringify([batch,source,'document-a',revision,hash.repeat(64)])
const key = reference()
const start = 1_800_000_000_000
const save = (values:FormValues,revision=0,change:Partial<Extract<DraftOperation,{type:'save'}>> = {}):DraftOperation =>
  ({type:'save',epoch:0,batch:'batch-a',key,scenarioId:form.id,values,revision,...change})
const read = (state:DraftState,batch='batch-a',epoch=0,now=start) =>
  applyDraftOperation(state,{type:'read',epoch,batch},now).drafts

describe('same-device form drafts',()=>{
  it('persists only explicitly allowed template fields',()=>{
    const result = applyDraftOperation(undefined,save({
      name:'测试姓名',studentId:'00004123',gender:'女',reason:'仅本次事由',phone:'联系方式',
      identity:'身份号码',address:'住址',photo:'照片',awardName1:'奖项',filename:'自定义文件名',confirm:'true',
    }),start)
    expect(result.saved).toEqual({key,scenarioId:'photo',revision:1,
      values:{name:'测试姓名',studentId:'00004123',gender:'女'},savedAt:start})
    expect(JSON.stringify(result.state)).not.toMatch(/原因|事由|身份号码|自定义文件名|奖项|照片|联系方式|confirm/)
    const unapproved = {...form,groups:[{title:'临时字段',fields:[
      {id:'reason',label:'自定义可复用字段',reusable:true},
      {id:'name',label:'敏感姓名',reusable:true,sensitive:true},
    ]}]}
    expect(recoverableFields(unapproved)).toEqual([])
  })

  it('round-trips leading zero values and excludes incompatible choices and lengths',()=>{
    const result = applyDraftOperation(undefined,save({name:'字'.repeat(13),gender:'未提供',studentId:'00001'}),start)
    expect(result.saved?.values).toEqual({studentId:'00001'})
  })

  it('allows recovery immediately before day seven, then prunes exactly at the deadline',()=>{
    const {state} = applyDraftOperation(undefined,save({name:'到期值'}),start)
    expect(read(state,'batch-a',0,start+draftRetentionMs-1)).toHaveLength(1)
    const expired = applyDraftOperation(state,{type:'read',epoch:0,batch:'batch-a'},start+draftRetentionMs)
    expect(expired.drafts).toEqual([])
    expect(expired.state.records).toEqual([])
  })

  it('renews only on another explicit save; reading does not slide the deadline',()=>{
    const {state} = applyDraftOperation(undefined,save({name:'第一次'}),start)
    const reopened = applyDraftOperation(state,{type:'open'},start+draftRetentionMs-1)
    expect(reopened.state).toBe(state)
    const renewedAt = start+60_000
    const renewed = applyDraftOperation(state,save({name:'第二次'},1),renewedAt)
    expect(read(renewed.state,'batch-a',0,start+draftRetentionMs)?.[0]?.values.name).toBe('第二次')
    expect(read(renewed.state,'batch-a',0,renewedAt+draftRetentionMs)).toEqual([])
  })

  it('prevents stale save after expiry or clear and keeps revisions distinct after recreation',()=>{
    const first = applyDraftOperation(undefined,save({name:'原记录'}),start)
    const expiredAt = start+draftRetentionMs
    expect(()=>applyDraftOperation(first.state,save({name:'过期页面'},1),expiredAt)).toThrow(DraftRevisionConflict)
    const cleared = applyDraftOperation(first.state,{type:'clear',epoch:0,batch:'batch-a'},start).state
    expect(read(cleared)).toEqual([])
    const recreated = applyDraftOperation(cleared,save({name:'新记录'}),start+1)
    expect(recreated.saved?.revision).toBe(2)
    expect(()=>applyDraftOperation(recreated.state,save({name:'过期页面'},1),start+1)).toThrow(DraftRevisionConflict)
  })

  it('separates batches, replacement source IDs, revisions and hashes',()=>{
    const alternates=[key,reference('batch-a','form-b'),reference('batch-a','form-a',1),reference('batch-a','form-a',0,'b')]
    const inOneBatch = alternates.reduce<DraftState | undefined>((state,referenceKey,index)=>
      applyDraftOperation(state,save({name:'测试'+index},0,{key:referenceKey}),start).state,undefined)!
    const {state} = applyDraftOperation(inOneBatch,
      save({name:'其他批次'},0,{batch:'batch-b',key:reference('batch-b')}),start)
    expect(read(state)?.map(draft=>draft.key)).toEqual(alternates)
    expect(read(state,'batch-b')).toHaveLength(1)
    const cleared = applyDraftOperation(state,{type:'clear',epoch:0,batch:'batch-a'},start).state
    expect(read(cleared,'batch-b')).toHaveLength(1)
    expect(()=>applyDraftOperation(state,save({},0,{batch:'batch-b'}),start)).toThrow('原件版本待核对')
  })

  it('rejects a stale revision and removes fields the user cleared before saving',()=>{
    const {state} = applyDraftOperation(undefined,save({name:'原记录',studentId:'00004123'}),start)
    const next = applyDraftOperation(state,save({name:'新记录',studentId:''},1),start+1)
    expect(()=>applyDraftOperation(next.state,save({name:'旧标签页'},1),start+1)).toThrow(DraftRevisionConflict)
    expect(read(next.state)?.[0].values).toEqual({name:'新记录'})
  })

  it('logout removes every batch and invalidates earlier account sessions including never-edited tabs',()=>{
    const initial = applyDraftOperation(undefined,save({name:'原记录'}),start).state
    const {state} = applyDraftOperation(initial,{type:'logout'},start)
    expect(state).toEqual({epoch:1,revision:0,records:[]})
    expect(()=>read(state)).toThrow(DraftSessionExpired)
    expect(()=>applyDraftOperation(state,save({name:'迟到的首次写入'},0),start)).toThrow(DraftSessionExpired)
    expect(read(state,'batch-a',1)).toEqual([])
    expect(applyDraftOperation(state,save({name:'重新登录的草稿'},0,{epoch:1}),start).saved?.values.name)
      .toBe('重新登录的草稿')
  })

  it('keeps only owner-specific legacy cleanup and validates the internal login destination',()=>{
    const records = new Set(['campusweave:form-draft:v1:owner-a:batch-a',
      'campusweave:form-draft:v1:owner-a:batch-b','campusweave:form-draft:v1:owner-b:batch-a','unrelated'])
    clearOwnerFormDrafts('owner-a',{
      get length(){return records.size},
      key:index=>Array.from(records)[index] ?? null,
      getItem:()=>null,setItem:()=>{},removeItem:key=>{records.delete(key)},
    })
    expect([...records]).toEqual(['campusweave:form-draft:v1:owner-b:batch-a','unrelated'])
    expect(savedDraftReturnPath('a1-b2')).toBe('/imports/a1-b2/forms')
    for (const input of ['',null,['batch-a'],'../cases','//other.example','x'.repeat(129)]) {
      expect(savedDraftReturnPath(input)).toBe('/home')
    }
    expect(readDraftReference(reference('batch-a','form-a',-1))).toBeUndefined()
  })
})
