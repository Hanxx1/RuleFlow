import {describe,expect,it} from 'vitest'
import {checkAssistantValue,proposedValue,type Plan} from './formAssistant'

const field = {id:'open',label:'如何验证本阶段结果？',type:'long' as const}
const plan:Plan = {
  id:'f0',meaning:'核验方案',expected:'说明后续如何复查',role:'applicant',required:'required',
  applicability:'applies',strategy:'generate',data_type:'long_text',ambiguous:false,
  bounds:{},requirements:[{source_id:'of0',quote:field.label}],facts:[],
}
describe('deterministic checks for a model-assisted form',()=>{
  it('accepts longer text for a lower bound even when the model reports an equal upper bound',()=>{
    const proposed={...plan,bounds:{min_chars:300,max_chars:300},
      requirements:[{source_id:'n1',quote:'该栏文字不少于300字'}]}
    expect(checkAssistantValue(field,proposed,'甲'.repeat(299)+'\n')).toContain('至少')
    expect(checkAssistantValue(field,proposed,'甲'.repeat(301))).toBe('')
    expect(checkAssistantValue({...field,max:299},proposed,'甲')).toContain('冲突')
    expect(checkAssistantValue(field,{...proposed,requirements:[{source_id:'n1',quote:'恰好300字'}]},
      '甲'.repeat(301))).toContain('最多')
  })
  it('distinguishes missing, unknown and explicitly inapplicable fields',()=>{
    const conditional={...plan,required:'conditional' as const,condition:'借用外部设备时填写'}
    expect(checkAssistantValue(field,conditional,'')).toContain('补齐')
    expect(checkAssistantValue(field,{...conditional,applicability:'unknown'},'')).toContain('待核对')
    expect(checkAssistantValue(field,{...conditional,applicability:'not_applicable'},'')).toBe('')
    expect(proposedValue({...conditional,role:'other',value:'修改审批栏'})).toBe('')
  })
  it('computes bounded operations and rejects invalid dates or duplicate operands',()=>{
    const operands=[{source_id:'a1',quote:'2026-10-01'},{source_id:'a1',quote:'2026-10-03'}]
    const calculate:Plan={...plan,calculation:{operation:'inclusive_days',operands}}
    expect(proposedValue(calculate)).toBe('3')
    expect(proposedValue({...calculate,calculation:{operation:'count',operands:[operands[0],operands[0]]}})).toBe('')
    expect(checkAssistantValue(field,{...plan,data_type:'date'},'2026-02-30')).toContain('有效日期')
    expect(checkAssistantValue(field,{...plan,data_type:'integer',bounds:{maximum_number:2}},'3')).toContain('数值上限')
    expect(checkAssistantValue({...field,choices:['本人','委托']},plan,'审核')).toContain('原表允许')
  })
})
