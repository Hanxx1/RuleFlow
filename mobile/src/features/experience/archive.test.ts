import {describe,expect,it} from 'vitest'
import {editExperiences,emptyExperience,experienceSource,normalizeExperience} from './archive'

const input = {...emptyExperience(),title:'  城市数据建模优秀奖 ',month:'2026-04',issuer:' 学院教务办 '}
const create = {id:'chosen-id',revision:0,input,confirmed:false}

describe('account experience archive',()=>{
  it('normalizes user input, keeping the award level unknown until supplied',()=>{
    expect(normalizeExperience(input)).toMatchObject({title:'城市数据建模优秀奖',issuer:'学院教务办',level:''})
  })

  it('checks required fields, dates, duration and content lengths',()=>{
    expect(()=>normalizeExperience({...input,title:' '})).toThrow('名称')
    expect(()=>normalizeExperience({...input,month:'2026-13'})).toThrow('年月')
    expect(()=>normalizeExperience({...input,kind:'project',endMonth:'2026-03'})).toThrow('结束年月')
    expect(()=>normalizeExperience({...input,hours:'1.99'})).toThrow('时长')
    expect(()=>normalizeExperience({...input,proofNote:'a'.repeat(201)})).toThrow('长度')
    expect(normalizeExperience({...input,kind:'practice',hours:'20.5',endMonth:'2026-04'}).hours).toBe('20.5')
  })

  it('allows saving an incomplete award for review and requires the issuer to confirm it',()=>{
    const incomplete = {...create,input:{...input,issuer:''}}
    expect(editExperiences([],incomplete)[0].confirmed).toBe(false)
    expect(()=>editExperiences([],{...incomplete,confirmed:true})).toThrow('颁奖单位')
  })

  it('updates by expected revision and keeps the earlier confirmed record intact',()=>{
    const before = editExperiences([],{...create,confirmed:true})
    const after = editExperiences(before,{...create,revision:1,input:{...input,title:'更正名称'}})
    expect(after[0]).toMatchObject({revision:2,title:'更正名称',confirmed:false})
    expect(experienceSource(before[0])).toEqual({
      id:'block:client:chosen-id',revision:1,quote:'2026-04 · 城市数据建模优秀奖 · 学院教务办',
    })
    expect(()=>editExperiences(after,{...create,revision:1})).toThrow('已被修改')
  })

  it('deletes only the matching record and rejects a stale update after deletion',()=>{
    const first = editExperiences([],create)
    const records = editExperiences(first,{...create,id:'keep'})
    const updated = editExperiences(records,{id:create.id,revision:1,remove:true})
    expect(updated.map(item=>item.id)).toEqual(['keep'])
    expect(()=>editExperiences(updated,{...create,revision:1})).toThrow('删除')
  })
})
