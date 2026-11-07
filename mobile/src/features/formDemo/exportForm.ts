import templateData from './templateData.json'
import {strFromU8,strToU8,unzipSync,zipSync} from 'fflate'
import {leaveDays,reviewForm,scenarioFields,validateFilename,type FormValues,type Scenario} from './scenarios'

const worksheet = 'xl/worksheets/sheet1.xml'
const document = 'word/document.xml'
const portrait = 'word/media/image1.png'
export const avatarUrl = 'data:image/png;base64,'+templateData['avatar.png']

const xmlText = (text: string) => text
  .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g,'')
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  .replace(/\r\n|\r|\n/g,'&#10;')

function formatted(value: string, isDate: boolean) {
  if (!isDate || !value) return value
  const [year,month,day] = value.split('-')
  return year+'年'+Number(month)+'月'+Number(day)+'日'
}

function columnIndex(address: string) {
  return [...address.replace(/\d/g,'')].reduce((index,char)=>index*26+char.charCodeAt(0)-64,0)
}

function fillWorksheet(xml: string, scenario: Scenario, values: FormValues) {
  const row = /(<row r="9"[^>]*>)(.*?)<\/row>/.exec(xml)
  if (!row) throw Error('演示模板缺少申请人录入行')
  const cells = new Map<string,string>()
  for (const match of row[2].matchAll(/<c r="([A-Z]+9)"[^>]*\/>/g)) cells.set(match[1],match[0])
  if ([...cells.values()].join('') !== row[2]) throw Error('演示模板录入行结构已变化')
  for (const field of scenarioFields(scenario)) {
    const address = field.cell
    const value = values[field.id]?.trim()
    if (!address || !value) continue
    const existing = cells.get(address)
    // The three list cells inherit their original column style when blank.
    if (!existing && !['H9','I9','L9'].includes(address)) throw Error('模板缺少 '+address)
    const start = existing?.slice(0,-2) || '<c r="'+address+'"'
    const encoded = xmlText(formatted(value,field.type==='date'))
    const cell = field.type === 'number'
      ? start+' t="n"><v>'+encoded+'</v></c>'
      : start+' t="inlineStr"><is><t xml:space="preserve">'+encoded+'</t></is></c>'
    cells.set(address,cell)
  }
  const filled = [...cells].sort(([a],[b])=>columnIndex(a)-columnIndex(b)).map(([,cell])=>cell).join('')
  return xml.slice(0,row.index)+row[1]+filled+'</row>'+xml.slice(row.index+row[0].length)
}

function fillDocument(xml: string, scenario: Scenario, values: FormValues) {
  const replacements = new Map(scenarioFields(scenario).filter(field=>field.export!==false).map(field=>[
    field.id, formatted(values[field.id]?.trim() || '',field.type==='date'),
  ]))
  if (scenario.id === 'leave') {
    replacements.set('className',(values.className || '').trim().replace(/班$/,''))
    replacements.delete('parentAware')
    replacements.set('awareYes',values.parentAware==='是'?'☑':'☐')
    replacements.set('awareNo',values.parentAware==='否'?'☑':'☐')
    replacements.set('days',String(leaveDays(values)))
  }
  if (scenario.id==='defer') {
    replacements.delete('courseMode')
    replacements.delete('halfDay')
    replacements.set('mainMode',values.courseMode==='主修'?'☑':'☐')
    replacements.set('retakeMode',values.courseMode==='重修'?'☑':'☐')
    replacements.set('minorMode',values.courseMode==='双学位、辅修'?'☑':'☐')
    replacements.set('morning',values.halfDay==='上午'?'☑':'☐')
    replacements.set('afternoon',values.halfDay==='下午'?'☑':'☐')
  }
  if (scenario.id==='exemption') {
    replacements.delete('exemptionKind')
    replacements.set('yearChange',values.exemptionKind==='年级异动'?'☑':'☐')
    replacements.set('majorChange',values.exemptionKind==='专业异动'?'☑':'☐')
    replacements.set('illness',values.exemptionKind==='因病'?'☑':'☐')
    if (values.exemptionKind!=='其他') replacements.set('otherReason','')
    if (values.studyBasis==='自学') {
      for (const field of ['completedCourse','completedCode','completedCredits','completedTeacher','completedGrade']) replacements.set(field,'')
    }
  }
  if (scenario.id==='photo') {
    replacements.delete('previousReplacement')
    replacements.set('previousYes',values.previousReplacement==='是'?'☑':'☐')
    replacements.set('previousNo',values.previousReplacement==='否'?'☑':'☐')
  }
  const replaced = new Set<string>()
  const result = xml.replace(/\{\{CW:([a-zA-Z0-9]+)\}\}/g,(_,key: string)=>{
    if (!replacements.has(key)) throw Error('演示模板字段未知')
    replaced.add(key)
    return xmlText(replacements.get(key) || '')
  })
  if (replaced.size !== replacements.size) throw Error('演示模板字段映射不完整')
  return result
}

function fromDataUrl(url: string) {
  return Uint8Array.from(atob(url.slice(url.indexOf(',')+1)),value=>value.charCodeAt(0))
}

export function buildForm(scenario: Scenario, values: FormValues, photo: string, stem: string) {
  if (Object.keys(reviewForm(scenario,values,Boolean(photo)).errors).length || validateFilename(stem)) {
    throw Error('请先补齐并检查表单和文件名')
  }
  const source = (templateData as Record<string,string>)[scenario.asset]
  if (!source) throw Error('离线模板缺失')
  const parts = unzipSync(fromDataUrl(source))
  if (scenario.format==='xlsx') {
    parts[worksheet] = strToU8(fillWorksheet(strFromU8(parts[worksheet]),scenario,values))
  } else {
    parts[document] = strToU8(fillDocument(strFromU8(parts[document]),scenario,values))
    if (scenario.photo==='embedded') {
      if (!photo.startsWith('data:image/png;base64,') || !parts[portrait]) throw Error('演示照片或模板槽位无效')
      parts[portrait] = fromDataUrl(photo)
    }
  }
  const mime = scenario.format==='xlsx'
    ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  const filename = (stem.startsWith('演示-') ? stem : '演示-'+stem)+'.'+scenario.format
  return {filename,blob:new Blob([zipSync(parts,{level:6}).slice().buffer],{type:mime})}
}
