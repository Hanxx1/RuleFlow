import type {Field} from './scenarios'

// These aliases describe fields across forms. They carry no file or school mapping.
const aliases: Record<string, readonly string[]> = {
  name:['姓名','申请人姓名','学生姓名','本人姓名'],
  gender:['性别'],
  studentId:['学号','学生学号','原学号'],
  identity:['身份证号','身份证号码','学籍历注册身份证号'],
  credential:['证件号','证件号码','证件编号'],
  phone:['联系电话','手机号码','手机号','手机','电话','申请人电话','本人电话','本人手机'],
  college:['学院','院系','所在学院','所在院系','所属学院'],
  major:['专业','所在专业','专业名称','所学专业'],
  className:['班级','所在班级'],
  year:['年级','所在年级'],
  birthDate:['出生日期','出生年月'],
  entryDate:['入学年月','入学时间','入学日期'],
  address:['家庭地址','通信地址','通讯地址','联系地址','家庭住址'],
  email:['邮箱','电子邮箱','电子邮件','常用E-mail','E-mail','Email'],
  exchangeInstitution:['境外院校/机构名称及所在国家或地区','境外院校名称及所在国家或地区'],
  postalCode:['邮编','邮政编码'],
  reason:['申请理由','申请原因','申请事由','申请补办原因','本人申请','申请事项及理由','原因','事由','更改理由'],
  statement:['情况说明','个人情况说明','申请情况说明','补充说明'],
  achievement:['个人总结','个人事迹','主要事迹'],
  semester:['学年学期','申请学期','学期'],
  applicationDate:['申请日期','申请时间','填表日期','填表时间'],
  type:['申请类型','申请类别','办理类别'],
}

export const normalizedLabel = (text: string) => text.normalize('NFKC').replace(/[\s():：]/g,'')
const protectedLabel = /签[字名章]|手签|盖章|按手印|审核|审批|意见|辅导员|指导教师|导师|班主任|推荐人|负责人|经办人|操作员|校医院|单位填写|学校填写|学院填写|院系填写|部门填写|公章|照片|贴照|证明材料|须知|^备注/

export function reservedLabel(text: string) {
  return protectedLabel.test(normalizedLabel(text))
}

export function startsProtectedSection(text: string) {
  const label = normalizedLabel(text)
  return /^(以下|[本此][栏区])?由(?!申请人|本人|学生|个人|填表人).{1,35}填写/.test(label) ||
    /^(学校|学院|院系|教务|校医院|财务|体育部|管理部门|审核单位|辅导员|导师).{0,14}(意见|审核|审批|填写)/.test(label) ||
    /^(辅导员|指导教师|导师|班主任|推荐人|负责人|经办人|审核人|审批人)(?:基本|联系|身份)?(?:信息|资料|栏|区)?$/.test(label)
}

const lengthNumber = '([0-9]{1,4})'
const lowerLimit = new RegExp('(?:不少于|不低于|不得少于|至少)\\s*'+lengthNumber+'\\s*字')
const upperLimit = new RegExp('(?:不超过|不得超过|最多|不多于)\\s*'+lengthNumber+'\\s*字|'+lengthNumber+'\\s*字以内')
const lengthRange = new RegExp(lengthNumber+'\\s*(?:至|[-—–~])\\s*'+lengthNumber+'\\s*字')
const exactLength = new RegExp('(?:恰好|正好)\\s*'+lengthNumber+'\\s*字')
const lengthInstruction = new RegExp('^(?:(?:字数(?:要求|为)?[：:]?)?\\s*(?:'+
  [lengthRange,lowerLimit,upperLimit,exactLength].map(rule=>rule.source).join('|')+')[\\s、,，;；]*)+$')

export function readTextLimits(text:string) {
  const normalized = text.normalize('NFKC')
  const matches = (rule:RegExp) => [...normalized.matchAll(new RegExp(rule.source,'g'))]
  const ranges = matches(lengthRange)
  const exact = matches(exactLength).map(match=>match[1])
  const minimums = [...ranges.map(match=>match[1]),...matches(lowerLimit).map(match=>match[1]),...exact].map(Number)
  const maximums = [...ranges.map(match=>match[2]),...matches(upperLimit).map(match=>match[1] ?? match[2]),...exact].map(Number)
  return {
    min:minimums.length ? Math.max(...minimums) : undefined,
    max:maximums.length ? Math.min(...maximums) : undefined,
  }
}

export function noticeLongField(text:string) {
  const normalized = normalizedLabel(text)
  const ids = [
    [/(?:申请|请假|缓考)(?:事项及)?(?:理由|事由|原因)/,'reason'],
    [/个人事迹|主要事迹|个人.{0,8}总结/,'achievement'],
    [/情况说明|补充说明/,'statement'],
  ] as const
  const matching = ids.filter(([pattern])=>pattern.test(normalized))
  return matching.length===1 ? matching[0][1] : undefined
}

export function detectField(raw: string, allowCustom = false): Field | undefined {
  if (reservedLabel(raw)) return
  const label = raw.trim().replace(/\s+/g,'').replace(/[：:]$/,'')
  const canonical = label.normalize('NFKC').replace(/\*+$/,'')
  const cleaned = canonical.replace(/\(([^()]*)\)/g,(original,inside:string)=>
    lengthInstruction.test(inside) ? '' : original)
  const suffix = /^(.*?)(?=字数|不少于|不低于|不得少于|至少|不超过|不得超过|最多|不多于|恰好|正好|\d)/.exec(cleaned)?.[0]
  const base = suffix && lengthInstruction.test(cleaned.slice(suffix.length)) ? suffix : cleaned
  const normalized = normalizedLabel(base).replace(/(?:非必填|选填|必填)$/,'')
  const semantic = Object.entries(aliases).find(([,names])=>names.includes(normalized))?.[0]
  if (!semantic && (!allowCustom || !/^[\p{L}\p{N}（）()／/、·]{2,16}$/u.test(base) ||
      /申请表|登记表|汇总表|材料清单|情况说明|^附件|^说明|^合计|^序号/.test(label))) return
  const limits = readTextLimits(raw)
  const long = semantic==='reason' || semantic==='achievement' || semantic==='statement' ||
    limits.min!==undefined || limits.max!==undefined
  const field: Field = {
    id:semantic || 'label-'+normalized,
    label,
    type:long ? 'long' : undefined,
    optional:/(?:非必填|选填)\s*[)）]?$/.test(raw.trim()),
    sensitive:Boolean(semantic && ['identity','credential','phone','address'].includes(semantic) ||
      /邮箱|e-?mail|QQ|微信|电话|手机|证件|身份证|住址|卡号|银行账号/i.test(normalized)),
    // The institution of an imported original has not been independently verified.
    reusable:semantic==='name' || semantic==='gender',
  }
  if (long) Object.assign(field,limits)
  return field
}

export function emptyPlaceholder(text: string) {
  return /^[\s_＿]*$/.test(text) || /^[（(]\s*(?:此处|请|在此|由申请人)\s*填写[^（）()]{0,32}[）)]$/.test(text.trim())
}

export function checkboxOptions(text: string) {
  const pattern = /([^\s□☐]+)[ \t]*[□☐]/g
  const options = [...text.matchAll(pattern)].map(match=>match[1])
  return options.length>=2 && new Set(options).size===options.length && !text.replace(pattern,'').trim() ? options : []
}
