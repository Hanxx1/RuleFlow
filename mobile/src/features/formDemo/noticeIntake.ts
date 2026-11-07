import {strFromU8,unzipSync} from 'fflate'
import templateData from './templateData.json'
import {isCompetitionNotice,scenarioFields,scenarios,type FormValues,type Scenario} from './scenarios'

export type AttachmentMatch = {name: string; scenario?: Scenario; error?: string}
export type NoticeEvidence = {line: number; text: string; kind: 'length' | 'filename' | 'photo' | 'review'}
type NamingRule = {parts: string[]; joiner: string; extension?: string}
export type NoticeRequirements = {
  evidence: NoticeEvidence[]
  lengths: Record<string,{min?:number;max?:number}>
  naming?: NamingRule
  physicalPhoto: boolean
  competition: boolean
  conflict: string
}

const fileLimit = 10*1024*1024
const textLimit = 30_000

export async function matchAttachment(file: File): Promise<AttachmentMatch> {
  const name = file.name
  if (!/\.(docx|xlsx)$/i.test(name)) return {name,error:'当前仅核对 DOCX、XLSX 原表。'}
  if (file.size>fileLimit || file.size<4) return {name,error:'文件大小不符合本机核对限制。'}
  const bytes = await file.arrayBuffer()
  const signature = new Uint8Array(bytes,0,4)
  if (signature.join(',')!=='80,75,3,4') return {name,error:'文件内容与 DOCX/XLSX 格式不符。'}
  const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
    .map(value=>value.toString(16).padStart(2,'0')).join('')
  const hashes: Record<string,string> = templateData.sourceHashes
  const scenario = scenarios.find(item=>hashes[item.id]===hash && name.toLowerCase().endsWith('.'+item.format))
  return scenario ? {name,scenario} : {name,error:'未核验此原件或版本。请核对校方空白原表，当前待人工映射。'}
}

export async function readNotice(file: File) {
  if (file.size>fileLimit) throw Error('通知文件超过本机处理限制。')
  let text: string
  if (/\.txt$/i.test(file.name)) {
    text = new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer())
  } else if (/\.docx$/i.test(file.name)) {
    const parts = unzipSync(new Uint8Array(await file.arrayBuffer()),{
      filter: entry=>entry.name==='word/document.xml' && entry.originalSize<1_000_000,
    })
    if (!parts['word/document.xml']) throw Error('无法读取 DOCX 通知正文。')
    const parsed = new DOMParser().parseFromString(strFromU8(parts['word/document.xml']),'application/xml')
    if (parsed.querySelector('parsererror')) throw Error('通知的 Word 正文结构无法读取。')
    const namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    text = [...parsed.getElementsByTagNameNS(namespace,'p')].map(p=>
      [...p.getElementsByTagNameNS(namespace,'t')].map(t=>t.textContent).join(''),
    ).join('\n')
  } else throw Error('请导入 UTF-8 TXT、DOCX 通知，或粘贴通知正文。')
  if (!text.trim() || text.length>textLimit) throw Error('通知正文为空或超过 30,000 字，请粘贴所需段落。')
  return text
}

function namingRule(text: string): NamingRule | undefined {
  // Naming rules for email, archives and scanned copies apply to different outputs.
  if (/邮件|主题|压缩包|扫描|PDF|签字后|所有材料|照片附件/i.test(text)) return
  const rule = /(?:命名为|文件名(?:为|格式[:：]?))\s*[“「"]([^”」"]{1,80})[”」"]/.exec(text)?.[1]
  if (!rule || !/(姓名|学号|学院|专业|班级)/.test(rule) || /[\/<>{}:?*]/.test(rule)) return
  const extension = /\.(docx|xlsx)$/i.exec(rule)?.[1].toLowerCase()
  const stem = extension ? rule.slice(0,-extension.length-1) : rule
  const plus = /[+＋]/.test(stem)
  if (stem.includes('.') || (plus && stem.includes('-'))) return
  const joiner = plus?'':'-'
  const parts = stem.split(plus?/[+＋]/:/-/).map(part=>part.trim())
  if (parts.length<2 || parts.some(part=>!part)) return
  return {parts,joiner,extension}
}

export function analyzeNotice(text: string): NoticeRequirements {
  const result: NoticeRequirements = {
    evidence:[],lengths:{},physicalPhoto:false,competition:isCompetitionNotice(text),conflict:'',
  }
  for (const [index,line] of text.split(/\r?\n/).entries()) {
    for (const raw of line.split(/[。；;]/)) {
      const text = raw.trim()
      if (!text) continue
      const evidence = {line:index+1,text:text.slice(0,260)}
      if (/文件名|命名/.test(text)) {
        const naming = namingRule(text)
        if (naming) {
          if (result.naming && JSON.stringify(result.naming)!==JSON.stringify(naming)) result.conflict = '通知存在不同命名规则，请核对适用附件。'
          result.naming = naming
        }
        result.evidence.push({...evidence,kind:naming?'filename':'review'})
        continue
      }
      if (/照片|贴照/.test(text) && /粘贴|贴照|贴.*照片|照片.*贴/.test(text) && !/免贴|无需|不(?:用|要)粘贴/.test(text)) {
        result.physicalPhoto = true
        result.evidence.push({...evidence,kind:'photo'})
        continue
      }
      const field = /(?:申请|请假|缓考)(?:理由|事由|原因)/.test(text)?'reason':/个人.*总结/.test(text)?'achievement':undefined
      if (field && /字/.test(text) && !/推荐理由|教师意见|院系意见|审核/.test(text)) {
        const range = /(\d{1,4})\s*(?:至|[-—–~～])\s*(\d{1,4})\s*字/.exec(text)
        const min = range?.[1] ?? /(?:不少于|不低于|至少)\s*(\d{1,4})\s*字/.exec(text)?.[1]
        const max = range?.[2] ?? /(?:不超过|不得超过|最多|不多于)\s*(\d{1,4})\s*字/.exec(text)?.[1] ?? /(\d{1,4})\s*字以内/.exec(text)?.[1]
        if (min || max) {
          const previous = result.lengths[field] || {}
          const constraint = {
            min:min ? Math.max(previous.min || 0,Number(min)) : previous.min,
            max:max ? Math.min(previous.max ?? Infinity,Number(max)) : previous.max,
          }
          if (constraint.min && constraint.max!==undefined && constraint.min>constraint.max) result.conflict = '通知的字数要求互相冲突，请核对。'
          result.lengths[field] = constraint
          result.evidence.push({...evidence,kind:'length'})
          continue
        }
      }
      if (/必须|必填|填写|格式|字体|字号|签字|手签|盖章|提交|截止|打印|照片|附件|证明|上传/.test(text)) {
        result.evidence.push({...evidence,kind:'review'})
      }
    }
  }
  return result
}

const namingFields: Record<string,string> = {姓名:'name',学号:'studentId',学院:'college',专业:'major',班级:'className'}

export function applyNotice(scenario: Scenario, requirements: NoticeRequirements) {
  let conflict = requirements.conflict
  const groups = scenario.groups.map(group=>({...group,fields:group.fields.map(field=>{
    const limit = requirements.lengths[field.id]
    if (!limit) return field
    const min = limit.min===undefined ? field.min : Math.max(field.min || 0,limit.min)
    const max = limit.max===undefined ? field.max : Math.min(field.max ?? Infinity,limit.max)
    if (min!==undefined && max!==undefined && min>max) conflict = field.label+'的通知要求和原表限制不一致，请核对。'
    return {...field,min,max}
  })}))
  if (requirements.physicalPhoto && !scenario.photo) conflict = '通知要求贴照，但此原表没有已核验的照片位置。请核对附件。'
  if (Object.keys(requirements.lengths).some(id=>!scenarioFields(scenario).some(field=>field.id===id))) {
    conflict = '通知的字数限制找不到对应字段，请核对所选附件。'
  }
  if (requirements.naming?.extension && requirements.naming.extension!==scenario.format) {
    conflict = '通知要求的文件格式与所选原表不同，请核对适用附件。'
  }
  if (requirements.naming?.parts.some(part=>namingFields[part] && !scenarioFields(scenario).some(field=>field.id===namingFields[part]))) {
    conflict = '通知的命名规则包含所选表格没有的字段，请核对适用附件。'
  }
  return {
    scenario:{...scenario,groups,photo:requirements.physicalPhoto && scenario.photo?'physical' as const:scenario.photo},
    conflict,
  }
}

export function noticeFilename(requirements: NoticeRequirements, values: FormValues) {
  if (!requirements.naming) return ''
  const parts = requirements.naming.parts.map(part=>namingFields[part] ? values[namingFields[part]]?.trim() : part)
  return parts.every(Boolean) ? parts.join(requirements.naming.joiner) : ''
}
