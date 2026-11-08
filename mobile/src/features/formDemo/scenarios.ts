import {additionalExamples,additionalScenarios} from './additionalScenarios'

export type Field = {
  id: string
  label: string
  type?: 'date' | 'long' | 'choice' | 'number'
  choices?: readonly string[]
  optional?: boolean
  sensitive?: boolean
  reusable?: boolean
  min?: number
  max?: number
  cell?: string
  hint?: string
  export?: false
}
export type FormValues = Record<string, string>
export type Scenario = {
  id: string
  title: string
  school: string
  institution?: string
  source: string
  asset: string
  format: 'xlsx' | 'docx'
  provenance: string
  groups: {title: string; fields: Field[]}[]
  manual: string
  printNote?: string
  photo?: 'physical' | 'embedded'
  photoNote?: string
}

const name: Field = {id:'name',label:'姓名',reusable:true,max:12}
const studentId: Field = {id:'studentId',label:'学号',reusable:true,max:40}
const college: Field = {id:'college',label:'院系',reusable:true,max:40}
const major: Field = {id:'major',label:'专业',reusable:true,max:40}
const gender: Field = {id:'gender',label:'性别',type:'choice',choices:['女','男'],reusable:true}
const phone: Field = {id:'phone',label:'联系电话',sensitive:true,max:11}
const identity: Field = {id:'identity',label:'身份证号',sensitive:true,max:18}
const date = (id: string, label: string): Field => ({id,label,type:'date'})
const long = (id: string, label: string, max: number, min?: number): Field => ({id,label,type:'long',max,min})
const choice = (id: string, label: string, choices: string[]): Field => ({id,label,type:'choice',choices})
const positive = (id: string, label: string): Field => ({id,label,type:'number'})
const cells = (map: [Field, string][]): Field[] => map.map(([field,cell])=>({...field,cell}))
const award = (index: number, addresses: string[], optional = false): Field[] => cells([
  [{id:'awardDate'+index,label:'获奖年月 '+index,optional,max:12},addresses[0]],
  [{id:'awardName'+index,label:'奖项名称 '+index,optional,max:88},addresses[1]],
  [{id:'awardIssuer'+index,label:'颁奖单位 '+index,optional,max:88},addresses[2]],
])

export const scenarios: Scenario[] = [
  {
    id:'scholarship',title:'国家奖学金申请',school:'南京审计大学学生工作处',
    source:'https://xgc.nau.edu.cn/2026/0924/c3439a162174/page.htm',
    asset:'scholarship.xlsx',format:'xlsx',provenance:'校方 XLSX 原模板',
    manual:'申请人手签、推荐理由、院系意见、盖章及相关审核日期由对应人员办理。',
    printNote:'原模板默认打印可能裁切申请理由。此文件用于可编辑电子版演示，纸质版待核对校方流程。',
    groups:[
      {title:'身份与学籍',fields:cells([
        [name,'A9'],[gender,'B9'],[identity,'C9'],[choice('studentType','学生类型',['本科']),'D9'],
        [college,'E9'],[major,'F9'],[{id:'birthMonth',label:'出生年月',max:12},'G9'],
        [{id:'ethnicity',label:'民族',max:12},'H9'],[choice('politics','政治面貌',['共青团员','群众','中共党员','中共预备党员']),'I9'],
        [studentId,'J9'],[{id:'enrollment',label:'入学年月',max:12},'K9'],
        [choice('duration','学制',['三年','四年','五年','六年']),'L9'],[{id:'grade',label:'年级',max:12},'M9'],
        [{id:'className',label:'班级',max:30,reusable:true},'N9'],[phone,'O9'],
      ])},
      {title:'2025—2026 学年成绩',fields:cells([
        [positive('rank','学习成绩名次'),'P9'],[positive('cohortSize','排名总人数'),'Q9'],
        [choice('evaluation','综合考评等级',['A+']),'R9'],[positive('passed','及格课程门数'),'S9'],
        [positive('requiredCourses','必修课门数'),'T9'],
      ])},
      {title:'获奖经历',fields:[
        ...award(1,['U9','V9','W9']),...award(2,['X9','Y9','Z9']),
        ...award(3,['AA9','AB9','AC9'],true),...award(4,['AD9','AE9','AF9'],true),
      ]},
      {title:'申请理由',fields:cells([[long('reason','申请理由',200,100),'AG9'],[date('applicationDate','申请日期'),'AH9']])},
    ],
  },
  {
    id:'leave',title:'学生请假申请',school:'广东财经大学金融学院',
    source:'https://finance.gdufe.edu.cn/12856/list.htm',
    asset:'leave.docx',format:'docx',provenance:'校方 2025 年 5 月更新 DOCX 原模板 · 学院联与任课教师联',
    manual:'班长、辅导员、学院及任课教师的签字和盖章由对应人员办理。两联同步填写。',
    printNote:'较长的输入可能改变分页，打印前请在 Word 中核对两联。',
    groups:[
      {title:'学生资料',fields:[name,studentId,major,{id:'className',label:'班级',max:30,reusable:true},phone]},
      {title:'本次请假',fields:[
        {id:'course',label:'课程',max:30},{id:'teacher',label:'任课教师',max:15},date('start','开始日期'),
        positive('startPeriod','起始节次'),date('end','结束日期'),positive('endPeriod','结束节次'),
        positive('periodCount','请假总节数'),long('reason','请假事由',100),
      ]},
      {title:'家长知情',fields:[
        {id:'guardian',label:'家长姓名',max:12,sensitive:true},
        {id:'guardianPhone',label:'家长手机号',max:11,sensitive:true},choice('parentAware','家长知情',['是','否']),
      ]},
    ],
  },
  {
    id:'proof',title:'学历及学位证明书申请',school:'广西中医药大学教务处',
    source:'https://www.gxtcmu.edu.cn/jwc/xzzx/xjxlxg/content_85207',
    asset:'proof.docx',format:'docx',provenance:'校方 2026 版 DOCX 原模板',
    manual:'申请人签名、学校审核、补发编号及办理日期由对应人员填写。',
    groups:[
      {title:'身份资料',fields:[name,gender,identity,{id:'hometown',label:'籍贯',max:15},{id:'ethnicity',label:'民族',max:12},phone,
        {id:'address',label:'工作单位或住址',sensitive:true,max:40}]},
      {title:'学籍与证书',fields:[date('start','入学日期'),date('end','毕业日期'),{id:'degree',label:'学位层次',max:12},major,
        {id:'certificate',label:'原学历证书编号',max:24,sensitive:true},
        {id:'degreeCertificate',label:'原学位证书编号',max:24,sensitive:true}]},
      {title:'本次申请',fields:[long('reason','申请理由',100),date('applicationDate','申请日期')]},
    ],
  },
  {
    id:'photo',title:'学生证补办登记',school:'南方科技大学学生工作部',
    source:'https://osa.sustech.edu.cn/affairs/283.html',
    asset:'photo.docx',format:'docx',provenance:'校方本科生补办 DOCX 原模板 · 一寸照片槽',
    manual:'申请人手签、辅导员签字和线下交件由对应人员办理。',
    photo:'physical',
    photoNote:'打印后将照片轻贴在原框内，按校方要求办理补证。',
    groups:[
      {title:'学生资料',fields:[name,studentId,gender,{id:'ethnicity',label:'民族',max:12},phone,
        {id:'residentialCollege',label:'书院',max:18},identity]},
      {title:'补办登记',fields:[{id:'address',label:'家庭地址',max:40,sensitive:true},{id:'railRoute',label:'乘车区间',max:25},
        choice('previousReplacement','以前是否补办过',['是','否']),long('reason','申请补发理由',100),date('applicationDate','申请日期')]},
    ],
  },
  ...additionalScenarios,
]

export const exampleIdentity: FormValues = {
  name:'林示例',studentId:'00001234',college:'数据科学学院',major:'数据科学与大数据技术',gender:'女',className:'数据科学一班',
}
export const exampleValues: Record<string, FormValues> = {
  ...additionalExamples,
  scholarship:{
    ...exampleIdentity,identity:'00000020050101000X',phone:'00000000000',studentType:'本科',birthMonth:'2005年1月',ethnicity:'汉族',
    politics:'共青团员',enrollment:'2024年9月',duration:'四年',grade:'2024级',rank:'3',cohortSize:'60',evaluation:'A+',passed:'12',
    requiredCourses:'12',awardDate1:'2025年11月',awardName1:'校级数据实践优秀项目',awardIssuer1:'示例大学教务处',
    awardDate2:'2026年5月',awardName2:'省级数据分析演示赛二等奖',awardIssuer2:'示例省学生竞赛组委会',
    reason:'本人认真完成本学年课程与实验，按周整理学习笔记，并主动复盘课程作业。课外参与数据实践项目，承担数据整理与结果核对工作，与同学分工完成展示。参加数据分析活动后，我进一步改进了记录方法。今后我将继续夯实专业基础，积极参与集体活动，把阶段性总结落实到日常学习中。',
    applicationDate:'2026-09-27',
  },
  leave:{...exampleIdentity,major:'金融学',className:'金融一班',phone:'00000000000',course:'统计学',teacher:'周示例',start:'2026-11-09',startPeriod:'1',
    end:'2026-11-11',endPeriod:'4',periodCount:'4',reason:'家庭急事',guardian:'林家长',guardianPhone:'00000000000',parentAware:'是'},
  proof:{...exampleIdentity,identity:'00000020000101000X',phone:'00000000000',hometown:'示例市',ethnicity:'汉族',address:'示例市明理路一号',
    start:'2018-09-01',end:'2022-06-30',degree:'学士',certificate:'000000001234567890',degreeCertificate:'000000001234567891',
    reason:'原证书遗失，现申请按学校流程补办学历及学位证明书。',applicationDate:'2026-11-07'},
  photo:{...exampleIdentity,phone:'00000000000',identity:'00000020050101000X',ethnicity:'汉族',residentialCollege:'示例书院',
    address:'示例市明理路一号',railRoute:'深圳北至示例站',previousReplacement:'否',reason:'原学生证遗失，现申请补办。',applicationDate:'2026-11-07'},
}

export function scenarioFields(scenario: Scenario) {
  return scenario.groups.flatMap(group=>group.fields)
}

export function reviewForm(scenario: Scenario, values: FormValues, hasPhoto: boolean) {
  const errors: Record<string,string> = {}
  const reminders: string[] = []
  for (const field of scenarioFields(scenario)) {
    const value = values[field.id]?.trim() || ''
    if (!value) {
      if (!field.optional) errors[field.id] = '请补充'+field.label
      continue
    }
    const length = [...value].length
    if (field.max && length > field.max) errors[field.id] = '最多填写 '+field.max+' 字'
    if (field.min && length < field.min) errors[field.id] = '至少填写 '+field.min+' 字'
    if (field.choices && !field.choices.includes(value)) errors[field.id] = '请选择模板允许的选项'
    if (field.type === 'number' && !/^[1-9]\d{0,5}$/.test(value)) errors[field.id] = '请填写正整数'
    if (field.type === 'date') {
      const parsed = new Date(value)
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0,10) !== value) errors[field.id] = '请填写有效日期'
    }
    if (field.id === 'identity' && !/^\d{17}[\dX]$/.test(value)) errors[field.id] = '请填写 18 位证件号码，末位 X 使用大写'
    if ((field.id === 'phone' || field.id === 'guardianPhone') && !/^\d{11}$/.test(value)) errors[field.id] = '请填写 11 位号码'
    if (['birthMonth','enrollment'].includes(field.id) || field.id.startsWith('awardDate')) {
      if (!/^\d{4}年(?:0?[1-9]|1[0-2])月$/.test(value)) errors[field.id] = '请使用 2025年9月 这样的格式'
    }
  }
  if (values.start && values.end && values.start > values.end) errors.end = '结束日期须晚于或等于开始日期'
  if (scenario.id === 'leave') {
    if (values.start === values.end && Number(values.startPeriod) > Number(values.endPeriod)) errors.endPeriod = '同日结束节次不能早于起始节次'
    if (values.parentAware === '否') errors.parentAware = '校方原表含家长知情声明，请确认后再导出。'
    if (values.parentAware === '是') reminders.push('学院联与任课教师联均填写家长知情状态。')
  }
  if (scenario.id === 'scholarship') {
    if (Number(values.rank) > Number(values.cohortSize)) errors.rank = '名次不能超过总人数'
    if (values.passed && values.requiredCourses && values.passed !== values.requiredCourses) errors.passed = '本模板要求及格门数与必修课门数一致'
    let lastAward = 0
    for (const index of [1,2,3,4]) {
      const ids = ['awardDate','awardName','awardIssuer'].map(id=>id+index)
      if (!ids.some(id=>values[id]?.trim())) continue
      for (const id of ids) if (!values[id]?.trim()) errors[id] = '请补齐这一组获奖经历'
      const match = /^(\d{4})年(\d{1,2})月$/.exec(values[ids[0]] || '')
      if (!match) continue
      const month = Number(match[1])*100 + Number(match[2])
      if (month < lastAward || month > 202608) errors[ids[0]] = '请按年月先后填写，最晚为 2026 年 8 月'
      lastAward = month
    }
  }
  if (scenario.photo==='embedded' && !hasPhoto) errors.photo = '请补充演示证件照'
  if (scenario.id==='resume') {
    const required = {
      '休学期满':'按原表说明另交休学申请原件。',
      '退役复学':'按原表说明另附退役证复印件。',
      '病愈复学':'按原表说明另附病愈情况证明复印件。',
    }
    const reminder = required[values.resumeKind as keyof typeof required]
    if (reminder) reminders.push(reminder)
  }
  if (scenario.id==='resume' && values.postalCode && !/^\d{6}$/.test(values.postalCode)) errors.postalCode = '请填写 6 位邮政编码'
  if (scenario.id==='exemption') {
    if (values.exemptionKind==='其他' && !values.otherReason?.trim()) errors.otherReason = '请补充其他原因'
    if (values.studyBasis==='已修课程') {
      for (const field of ['completedCourse','completedCode','completedCredits','completedTeacher','completedGrade']) {
        if (!values[field]?.trim()) errors[field] = '请补充已修课程资料'
      }
    }
  }
  return {errors,reminders}
}

export function leaveDays(values: FormValues) {
  return (Date.parse(values.end) - Date.parse(values.start))/86_400_000 + 1
}

export function proposedFilename(scenario: Scenario, values: FormValues) {
  const name = values.name?.trim() || '待填姓名'
  return '演示-'+[scenario.title,name,values.studentId?.trim()].filter(Boolean).join('-')
}

export function validateFilename(stem: string) {
  if (!stem.trim() || stem.length > 90 || /[<>:"/\\|?*\u0000-\u001f]|[. ]$/.test(stem) ||
      /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(stem)) return '请填写有效文件名，最多 90 字，并避免路径符号。'
  return ''
}

export function isCompetitionNotice(text: string) {
  return /竞赛|比赛|赛事|联赛|挑战杯/.test(text) && /截止|时间|提交|报送|材料/.test(text)
}
