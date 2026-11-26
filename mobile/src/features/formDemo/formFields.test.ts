import {describe,expect,it} from 'vitest'
import {checkboxOptions,detectField,emptyPlaceholder,reservedLabel,startsProtectedSection} from './formFields'

describe('generic form field evidence',()=>{
  it('separates applicant aliases from protected roles',()=>{
    expect(detectField('申 请 人 姓 名')?.id).toBe('name')
    expect(detectField('学　号')).toMatchObject({id:'studentId',reusable:false})
    expect(detectField('身份证号')).toMatchObject({id:'identity',sensitive:true})
    expect(detectField('联系电话（选填）')).toMatchObject({id:'phone',optional:true})
    expect(detectField('辅导员联系电话',true)).toBeUndefined()
    expect(startsProtectedSection('以下由办公室填写')).toBe(true)
    expect(startsProtectedSection('以下由学生填写')).toBe(false)
    expect(reservedLabel('申请人签名')).toBe(true)
    expect(startsProtectedSection('辅导员基本信息')).toBe(true)
    expect(startsProtectedSection('推荐人联系资料')).toBe(true)
    expect(startsProtectedSection('申请人信息')).toBe(false)
  })

  it('reads a form-specific label and an explicit character range',()=>{
    expect(detectField('修读保健班期限',true)?.id).toBe('label-修读保健班期限')
    expect(detectField('申请理由（180–220字）')).toMatchObject({id:'reason',min:180,max:220,type:'long'})
    expect(detectField('附件一申请表',true)).toBeUndefined()
  })

  it('accepts only bounded placeholders and unambiguous checkbox lists',()=>{
    expect(emptyPlaceholder('（请填写学号）')).toBe(true)
    expect(emptyPlaceholder('填写说明：请核对后签字')).toBe(false)
    expect(checkboxOptions('休学□  保留入学□  退学□')).toEqual(['休学','保留入学','退学'])
    expect(checkboxOptions('休学□  复学□（需审核）')).toEqual([])
  })

  it('masks contact and credential values in generic form previews',()=>{
    expect(detectField('手机')).toMatchObject({id:'phone',sensitive:true})
    expect(detectField('电子邮箱',true)).toMatchObject({sensitive:true})
    expect(detectField('微信号',true)).toMatchObject({sensitive:true})
    expect(detectField('交行卡号*',true)).toMatchObject({id:'label-交行卡号',sensitive:true,reusable:false})
    expect(detectField('常用E-mail')).toMatchObject({id:'email',sensitive:true})
    expect(detectField('修读保健班期限',true)).toMatchObject({sensitive:false})
  })
})
