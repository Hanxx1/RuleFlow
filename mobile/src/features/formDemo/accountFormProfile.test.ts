import {describe,expect,it} from 'vitest'
import {emptyWorkspace,formAssertions} from '../../services/clientWorkspace'
import {applyProfileCandidates,reviewAccountProfile,staleProfileLabels} from './accountFormProfile'
import {scenarios} from './scenarios'

const form = scenarios.find(item=>item.id==='scholarship')!
const proof = scenarios.find(item=>item.id==='proof')!
const today = '2026-11-25'
const school = formAssertions({school:'南京审计大学'})
const review = (additional: ReturnType<typeof formAssertions>,caseId='',current={})=>
  reviewAccountProfile({...emptyWorkspace('test-a'),assertions:[...school,...additional]},form,caseId,current,today)
const sample = formAssertions({college:'工程学院',major:'计算机科学',class_name:'软件一班',student_type:'undergraduate'})

describe('confirmed account profile for form completion',()=>{
  it('offers only supported applicant fields and attaches their actual profile references',()=>{
    const result = review(sample)
    expect(result.candidates.map(item=>[item.id,item.value])).toEqual([
      ['studentType','本科'],['college','工程学院'],['major','计算机科学'],['className','软件一班'],
    ])
    const major = result.candidates.find(item=>item.id==='major')!
    expect(major.refs.map(source=>source.id)).toEqual([sample[1].id,school[0].id])
    expect(major.refs[0].quote).toContain('计算机科学')
  })

  it('requires an explicit matching school and a writable slot on an unfamiliar original',()=>{
    const workspace = {...emptyWorkspace('generic-user'),assertions:[...school,...sample]}
    const generic = {...form,id:'imported-template',school:''}
    expect(reviewAccountProfile(workspace,generic,'',{},today).candidates).toEqual([])
    generic.school='其他学校'
    expect(reviewAccountProfile(workspace,generic,'',{},today).candidates).toEqual([])
    generic.school='南京审计大学'
    const selected=reviewAccountProfile(workspace,generic,'',{major:'手填专业'},today).candidates
    expect(selected.some(item=>item.id==='major')).toBe(false)
    expect(selected.find(item=>item.id==='college')?.refs.map(ref=>ref.id)).toEqual([sample[0].id,school[0].id])
    const changed={...workspace,assertions:[...school,...formAssertions({college:'新院系'})]}
    expect(staleProfileLabels(selected,reviewAccountProfile(changed,generic,'',{},today).candidates)).toContain('院系')
  })

  it('rejects another school and templates for historical credentials',()=>{
    const profile = {...emptyWorkspace('test-a'),assertions:formAssertions({school:'其他学校',major:'外校专业'})}
    expect(reviewAccountProfile(profile,form,'',{},today)).toMatchObject({candidates:[],issue:'画像学校与此原表适用的学校不同，仍可手工填写。'})
    expect(reviewAccountProfile(profile,proof,'',{},today)).toMatchObject({candidates:[],issue:'此模板暂无可从当前学籍画像带入的字段。'})
  })

  it('requires a confirmed and unambiguous school, even when a raw profile value is present',()=>{
    const profile = {...emptyWorkspace('test-a'),form:{school:'南京审计大学'},assertions:sample}
    expect(reviewAccountProfile(profile,form,'',{},today).issue).toContain('缺少')
    expect(review([...sample,...formAssertions({school:'其他学校'})]).issue).toContain('冲突')
  })

  it('skips expired, unconfirmed and conflicting facts without downgrading them to values',()=>{
    const expired = formAssertions({college:'旧学院'},'', '2026-11-24')
    const unfinished = formAssertions({major:'未确认专业'}).map(item=>({...item,confirmed:false}))
    const conflict = [...formAssertions({class_name:'旧班'}),...formAssertions({class_name:'新班'})]
    expect(review([...expired,...unfinished,...conflict]).candidates).toEqual([])
  })

  it('accepts a fact through its expiry date and only within its matching Case',()=>{
    const scoped = formAssertions({college:'事项学院'},'case-a',today)
    expect(review(scoped,'case-b').candidates).toEqual([])
    expect(review(scoped).candidates).toEqual([])
    expect(review(scoped,'case-a').candidates.map(item=>item.value)).toEqual(['事项学院'])
  })

  it('skips profile values outside the template’s choices and max length',()=>{
    const facts = formAssertions({student_type:'graduate',college:'长'.repeat(41)})
    expect(review(facts).candidates).toEqual([])
    expect(review(facts).skipped).toEqual(expect.arrayContaining(['学生类型','院系']))
  })

  it('never overwrites a field entered before or during profile review, and respects deselection',()=>{
    const result = review(sample,'',{major:'已填写专业'})
    expect(result.candidates.some(item=>item.id==='major')).toBe(false)
    expect(applyProfileCandidates({college:'审阅时手填'},result.candidates,['college','studentType'])
      .map(item=>item.id)).toEqual(['studentType'])
  })

  it('recognizes expired or out-of-scope sources at export, even if the new value happens to match',()=>{
    const scoped = formAssertions({college:'事项学院'},'case-a',today)
    const applied = review(scoped,'case-a').candidates
    const moved = formAssertions({college:'事项学院'},'case-b',today)
    expect(staleProfileLabels(applied,review(scoped,'case-a').candidates)).toEqual([])
    expect(staleProfileLabels(applied,review(moved,'case-b').candidates)).toEqual(['院系'])
    const profile = {...emptyWorkspace('test-a'),assertions:[...school,...scoped]}
    expect(staleProfileLabels(applied,reviewAccountProfile(profile,form,'case-a',{},'2026-11-26').candidates)).toEqual(['院系'])
  })
})
