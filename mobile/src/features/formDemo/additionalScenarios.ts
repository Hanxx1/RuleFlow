import type {Field,FormValues,Scenario} from './scenarios'

const name: Field = {id:'name',label:'姓名',reusable:true,max:12}
const studentId: Field = {id:'studentId',label:'学号',reusable:true,max:24}
const college: Field = {id:'college',label:'所在学院',reusable:true,max:24}
const major: Field = {id:'major',label:'当前专业',reusable:true,max:24}
const className: Field = {id:'className',label:'班级',reusable:true,max:16}
const phone: Field = {id:'phone',label:'本人联系电话',sensitive:true,max:11}
const gender: Field = {id:'gender',label:'性别',type:'choice',choices:['女','男'],reusable:true}
const reason = (label: string,max: number): Field => ({id:'reason',label,type:'long',max})
const date = (id: string,label: string): Field => ({id,label,type:'date'})
const choice = (id: string,label: string,choices: string[]): Field => ({id,label,type:'choice',choices})
const applicationDate = date('applicationDate','申请日期')
const guardian = {id:'guardian',label:'家长姓名',sensitive:true,max:12}
const guardianPhone = {id:'guardianPhone',label:'家长联系电话',sensitive:true,max:11}

export const additionalScenarios: Scenario[] = [
  {
    id:'stay',title:'假期留校住宿',school:'华北水利水电大学学生工作部',institution:'ncwu',
    source:'https://www2.ncwu.edu.cn/xsc/info/1013/4085.htm',
    asset:'stay.docx',format:'docx',provenance:'2026 年暑假 DOCX 原表 · 附件 1',
    manual:'本人签字和审批留空。双面打印，并按通知另备家长知情同意书。',
    photo:'physical',photoNote:'可按校方要求在打印后粘贴近期一寸免冠照。此导出选择纸质贴照流程。',
    groups:[
      {title:'申请人',fields:[name,gender,college,studentId,major,phone,{id:'room',label:'原宿舍号',max:16},guardian,guardianPhone]},
      {title:'留校安排',fields:[reason('暑假留校理由',80),date('start','留校开始日期'),date('end','留校结束日期'),applicationDate]},
    ],
  },
  {
    id:'defer',title:'课程缓考',school:'广东工业大学教务处',
    source:'https://jwc.gdut.edu.cn/info/1234/3657.htm',
    asset:'defer.docx',format:'docx',provenance:'校方线下缓考 DOCX 原表 · 三联',
    manual:'教务处联、学院联、学生回执同步填入学生字段；资格、意见和签字由相关人员办理。',
    groups:[
      {title:'学生资料',fields:[name,studentId,college,major,className,phone]},
      {title:'本次课程考试',fields:[
        {id:'course',label:'缓考课程',max:18},
        choice('courseMode','修读类型',['主修','重修','双学位、辅修']),
        {id:'examWeek',label:'考试周次',type:'number',max:2},
        choice('weekday','星期',['一','二','三','四','五','六','日']),
        choice('halfDay','考试时段',['上午','下午']),reason('缓考申请理由',60),applicationDate,
      ]},
    ],
  },
  {
    id:'workstudy',title:'勤工助学优秀个人申请',school:'南开大学物理科学学院',
    source:'https://physics.nankai.edu.cn/_t12/2026/0622/c572a598773/page.htm',
    asset:'workstudy.docx',format:'docx',provenance:'2025–2026 学年度 DOCX 原表 · 附件 1',
    manual:'个人总结附页随申请表导出。推荐意见、手签和盖章由相应人员办理。原通知的邮件命名要求在来源页核对。',
    groups:[
      {title:'基本资料',fields:[name,studentId,college,phone,{id:'job',label:'所在岗位',max:25},
        {id:'department',label:'所在部门',max:25},choice('politics','政治面貌',['共青团员','中共党员','中共预备党员','群众','其他'])]},
      {title:'工作经历与总结',fields:[
        {id:'learnings',label:'对勤工助学工作的理解和收获',type:'long',max:140},
        {id:'achievement',label:'个人工作突出事迹总结',type:'long',min:200,max:520},
        {id:'suggestions',label:'对勤工助学工作的建议',type:'long',max:140},
      ]},
    ],
  },
  {
    id:'resume',title:'学生复学申请',school:'华北水利水电大学继续教育学院',institution:'ncwu',
    source:'https://www2.ncwu.edu.cn/jixujiaoyu/info/1202/2140.htm',
    asset:'resume.docx',format:'docx',provenance:'校方 DOCX 原表 · 继续教育学院',
    manual:'申请人手签按手印，学院意见由学校填写。根据复学原因准备校方要求的凭证。',
    groups:[
      {title:'原学籍资料',fields:[name,gender,studentId,phone,{id:'address',label:'家庭地址',sensitive:true,max:40},
        {id:'postalCode',label:'邮政编码',max:6}]},
      {title:'本人申请',fields:[
        {...choice('resumeKind','复学情形',['休学期满','退役复学','病愈复学']),export:false},
        {...reason('复学申请（含拟复学时间）',90),hint:'如篇幅不足，校方原表允许另附详细申请。'},
        applicationDate,
      ]},
    ],
  },
  {
    id:'major',title:'转专业申请',school:'开封职业学院教务处',
    source:'https://jwc.kfvc.edu.cn/2025/1215/c77a8047/page.htm',
    asset:'major.docx',format:'docx',provenance:'2025–2026 学年通知 DOCX 原表 · 附件 2',
    manual:'按通知另备手写申请书；拟转入班级和各级审批由相应单位填写。',
    groups:[
      {title:'当前学籍',fields:[name,gender,studentId,college,major,className,phone,{id:'identity',label:'身份证号',max:18,sensitive:true}]},
      {title:'本次申请',fields:[{id:'targetMajor',label:'拟转入专业',max:28},reason('申请转专业原因',130),applicationDate]},
    ],
  },
  {
    id:'review',title:'成绩查分查卷',school:'四川建筑职业技术大学教务处',institution:'scac',
    source:'https://www.scac.edu.cn/jwc/info/1160/1681.htm',
    asset:'review.docx',format:'docx',provenance:'校方 DOCX 原表 · 成绩发布后使用',
    manual:'任课教师按原表办理查分查卷；查分结果、成绩更改及审批由校方填写。',
    groups:[
      {title:'学生与学期',fields:[name,studentId,college,className,phone,{id:'academicYear',label:'学年',max:14},
        choice('term','学期',['第一','第二']),applicationDate]},
      {title:'课程及申请原因',fields:[
        {id:'course',label:'课程名称',max:20},{id:'courseCode',label:'课程代码',max:16},
        choice('assessment','考核方式',['考试','考查']),{id:'offeringUnit',label:'开课单位',max:20},
        {id:'teacher',label:'任课教师',max:12},{id:'teacherPhone',label:'教师电话',sensitive:true,max:20},reason('成绩更正申请原因',80),
      ]},
    ],
  },
  {
    id:'exemption',title:'学生课程免修',school:'四川建筑职业技术大学教务处',institution:'scac',
    source:'https://www.scac.edu.cn/jwc/info/1160/1681.htm',
    asset:'exemption.docx',format:'docx',provenance:'校方 2026 年 10 月 DOCX 原表',
    manual:'按原表要求处理学籍异动认定表和三份交件。审批及盖章由对应人员办理。',
    groups:[
      {title:'学生与学期',fields:[name,studentId,college,className,{id:'academicYear',label:'学年',max:14},
        choice('term','学期',['第一','第二']),applicationDate]},
      {title:'免修课程',fields:[
        choice('exemptionKind','免修原由',['年级异动','专业异动','因病','其他']),
        {id:'otherReason',label:'其他原因',max:30,optional:true},
        {id:'course',label:'课程名称',max:20},{id:'courseCode',label:'课程代码',max:16},
        {id:'credits',label:'学分',max:5},{id:'teacher',label:'任课教师',max:12},
        {id:'hours',label:'学时',type:'number',max:4},reason('免修课程理由',100),
      ]},
      {title:'已修课程',fields:[
        {...choice('studyBasis','学习依据',['已修课程','自学']),export:false},
        {id:'completedCourse',label:'已修课程名称',optional:true,max:20},
        {id:'completedCode',label:'已修课程代码',optional:true,max:16},
        {id:'completedCredits',label:'已修学分',optional:true,max:5},
        {id:'completedTeacher',label:'已修课程教师',optional:true,max:12},
        {id:'completedGrade',label:'已修课程成绩',optional:true,max:12},
      ]},
    ],
  },
]

const student = {name:'林示例',studentId:'00001234',gender:'女',college:'示例学院',major:'数据科学',className:'数据一班',phone:'00000000000'}
export const additionalExamples: Record<string,FormValues> = {
  stay:{...student,room:'示例楼 203',guardian:'林示例家长',guardianPhone:'00000000000',
    reason:'暑假留校完成课程设计。',start:'2026-07-08',end:'2026-07-20',applicationDate:'2026-06-28'},
  defer:{...student,course:'数据分析',courseMode:'主修',examWeek:'18',weekday:'三',halfDay:'上午',
    reason:'因家庭突发情况无法按时参加课程考试。',applicationDate:'2026-06-15'},
  workstudy:{...student,department:'校内服务中心',job:'资料助理',politics:'共青团员',
    learnings:'在资料整理中理解了记录准确、交接清楚的重要性。',
    achievement:'我在示例岗位协助整理预约记录和学习资料。开始时，每次交接只在口头说明，接班同学需要重复核对。后来我先按日期、事项和状态整理记录，再请负责老师检查字段，补齐容易遗漏的处理时间。遇到临时变更时，我会更新记录并告知下一位同学。为减少反复询问，我将常见问题按办理步骤归类，把需要老师确认的事项单独列出。学期结束前，我和同学一起抽查样表、修正不清楚的说明，并按岗位要求交接。通过这些工作，我学会把日常事务拆成可以核对的步骤，也更加重视保管资料和保护同学信息。今后我会继续改进记录方式，及时反馈问题并认真完成交接。',
    suggestions:'建议增加岗位交接样例和常见问题说明。'},
  resume:{...student,address:'示例市明理路一号',postalCode:'000000',resumeKind:'休学期满',
    reason:'本人休学期已满，申请于2026年9月复学。',applicationDate:'2026-08-21'},
  major:{...student,identity:'00000020050101000X',targetMajor:'信息管理',
    reason:'希望转入信息管理专业，继续学习数据管理与信息系统课程。',applicationDate:'2025-12-18'},
  review:{...student,academicYear:'2025–2026',term:'第二',applicationDate:'2026-07-03',course:'统计学',courseCode:'000123',
    assessment:'考试',offeringUnit:'示例教学单位',teacher:'周示例',teacherPhone:'00000000000',
    reason:'课程成绩与本人记录有差异，申请核对期末成绩。'},
  exemption:{...student,academicYear:'2026–2027',term:'第一',applicationDate:'2026-10-15',
    exemptionKind:'专业异动',course:'统计学',courseCode:'000123',credits:'2.5',teacher:'周示例',hours:'40',
    reason:'此前已修同类课程，申请校方认定后免修。',studyBasis:'已修课程',completedCourse:'应用统计学',
    completedCode:'000099',completedCredits:'3',completedTeacher:'张示例',completedGrade:'86'},
}
