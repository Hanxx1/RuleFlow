import {strFromU8,strToU8,unzipSync,zipSync} from 'fflate'
import {checkboxOptions,detectField,emptyPlaceholder,normalizedLabel,reservedLabel,startsProtectedSection} from './formFields'
import {reviewForm,validateFilename,type Field,type FormValues,type Scenario} from './scenarios'
import {officeFilename,officeMime} from './officeDelivery'

const word = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const sheet = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
const rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
const xml = 'http://www.w3.org/XML/1998/namespace'
const mainWord = 'word/document.xml'
const workbook = 'xl/workbook.xml'
const relationshipNS = 'http://schemas.openxmlformats.org/package/2006/relationships'
const contentNS = 'http://schemas.openxmlformats.org/package/2006/content-types'
type Format = Scenario['format']
type Package = Record<string,Uint8Array>
type Mode = 'paragraph' | 'wordText' | 'cell'
type Slot = {
  part: string; path: number[]; where: string; mode: Mode
  prefix?: string; suffix?: string; checks?: string
}
type FormSection = {id:string; label:string}
type Candidate = {field:Field; label:string; where:string; context?:string; slot?:Slot; section?:FormSection}
export type GenericForm = {
  name: string; format: Format; bytes: Uint8Array
  fields: {id:string; candidates:Candidate[]}[]
  manual: {where:string; text:string}[]
  sections: FormSection[]
  photoSlot: boolean
}
export type GenericMappingSelection = {choices:Record<string,string>; section?:string; school?:string}
export type GenericMapping = GenericMappingSelection & {form:GenericForm}
type Layout = {fields:Candidate[]; manual:GenericForm['manual']; photoSlot:boolean}

const children = (element: Element | undefined | null, ns: string, tag: string) =>
  Array.from(element?.children || []).filter(child=>child.namespaceURI===ns && child.localName===tag)
const nodes = (element: Document | Element, ns: string, tag: string) =>
  Array.from(element.getElementsByTagNameNS(ns,tag))
const first = (element: Element | undefined | null, ns: string, tag: string) => children(element,ns,tag)[0]

function parse(bytes: Uint8Array, ns: string, root: string) {
  const source = strFromU8(bytes)
  if (/<!DOCTYPE|<!ENTITY/i.test(source)) throw Error('原表包含不支持的 XML 声明。')
  const doc = new DOMParser().parseFromString(source,'application/xml')
  if (doc.documentElement.localName!==root || doc.documentElement.namespaceURI!==ns || doc.querySelector('parsererror')) {
    throw Error('原表的 Office XML 结构无法读取。')
  }
  return doc
}

function readPackage(bytes: Uint8Array) {
  let count = 0
  let size = 0
  const names = new Set<string>()
  const parts = unzipSync(bytes,{filter:entry=>{
    count++
    size += entry.originalSize
    if (count>320 || size>24*1024*1024 || entry.originalSize>8*1024*1024) throw Error('原表解压后超过本机核对限制。')
    if (names.has(entry.name) || /(^\/|\\|(^|\/)(\.\.|__proto__|constructor)(\/|$)|^_xmlsignatures\/|vbaProject|\/(activeX|embeddings|externalLinks)\/)/i.test(entry.name)) {
      throw Error('原表含重复条目、签名或需要保留的高级 Office 组件，请在 Office 中填写。')
    }
    names.add(entry.name)
    return true
  }})
  if (!parts['[Content_Types].xml'] || !parts['_rels/.rels']) throw Error('文件不是有效的 Office 原表。')
  return parts
}

function pathTo(element: Element) {
  const path: number[] = []
  for (let node=element; node.parentElement; node=node.parentElement) {
    path.unshift(Array.from(node.parentElement.children).indexOf(node))
  }
  return path
}

function atPath(doc: Document, path: number[]) {
  let element: Element | undefined = doc.documentElement
  for (const index of path) element = element?.children[index]
  if (!element) throw Error('原表位置已失效，请重新核对。')
  return element
}

function location(part: string, element: Element, mode: Mode, where: string): Slot {
  return {part,path:pathTo(element),mode,where}
}

const wordText = (element: Element) => nodes(element,word,'t').map(node=>node.textContent || '').join('')
const cellText = (cell: Element) => children(cell,word,'p').map(wordText).join('\n')
const plainParagraph = (paragraph: Element) => Array.from(paragraph.children).every(item=>
  item.namespaceURI===word && (item.localName==='pPr' || (item.localName==='r' &&
    Array.from(item.children).every(child=>child.namespaceURI===word && ['t','rPr'].includes(child.localName)))))

function wordInput(cell: Element | undefined, long: boolean) {
  if (!cell || first(first(cell,word,'tcPr'),word,'vMerge') || first(cell,word,'tbl')) return undefined
  const paragraphs = children(cell,word,'p')
  if (!paragraphs.length || Array.from(cell.children).some(item=>item.namespaceURI!==word || !['p','tcPr'].includes(item.localName))) return undefined
  const paragraph = paragraphs[0]
  if (!plainParagraph(paragraph) || !emptyPlaceholder(wordText(paragraph))) return undefined
  const rest = paragraphs.slice(1).map(wordText).join('\n').trim()
  if (rest && (!long || !/^(本人承诺|申请人[：:]|签字|本人签名|申请人签名|本人声明)/.test(rest) ||
      /审核|审批|学院意见|教师意见|盖章/.test(rest))) return undefined
  return paragraph
}

function wordFullRow(row: Element | undefined) {
  const cells = children(row,word,'tc')
  if (cells.length!==1 || first(first(row,word,'trPr'),word,'gridBefore') ||
      first(first(row,word,'trPr'),word,'gridAfter')) return undefined
  const cell = cells[0]
  const properties = first(cell,word,'tcPr')
  if (first(properties,word,'vMerge') || first(properties,word,'hMerge')) return undefined
  return {cell,span:first(properties,word,'gridSpan')?.getAttributeNS(word,'val') || '1'}
}

function canExpand(row: Element | undefined) {
  return !children(first(row,word,'trPr'),word,'trHeight')
    .some(height=>height.getAttributeNS(word,'hRule')==='exact')
}

function openField(label:string, where:string):Field | undefined {
  const clean = label.trim()
  if (!clean || clean.length>240 || reservedLabel(clean) || !/\p{L}/u.test(clean) ||
      /^(?:说明|填写须知|提示|示例|附件|第.{1,8}部分)[：:]|(?:申请表|登记表|报名表)$/.test(clean)) return
  return {id:'label-open-'+where, label:clean, type:'long', optional:true}
}

function inlineField(text: string) {
  const match = /^(.{1,24}?[：:])([\s_＿]*(?:-\s*学年第\s*学期)?[\s_＿]*)$/s.exec(text)
  if (!match) return
  const field = detectField(match[1])
  if (field) return {field,prefix:match[1]}
}

function pushManual(layout: Layout, where: string, text: string) {
  if (/照片|贴照/.test(text)) layout.photoSlot = true
  if (layout.manual.length<30) layout.manual.push({where,text:text.trim().slice(0,160)})
}

function wordLayout(parts: Package): Layout {
  const doc = parse(parts[mainWord],word,'document')
  const protections = parts['word/settings.xml']
    ? nodes(parse(parts['word/settings.xml'],word,'settings'),word,'documentProtection') : []
  if (protections.some(item=>!['0','false','off'].includes(item.getAttributeNS(word,'enforcement') || ''))) {
    throw Error('此 Word 原表启用了文档保护，请在 Office 中填写。')
  }
  const body = first(doc.documentElement,word,'body')
  const layout: Layout = {fields:[],manual:[],photoSlot:false}
  let tableNumber = 0
  let protectedSection = false
  for (const element of Array.from(body?.children || [])) {
    if (element.namespaceURI!==word) continue
    if (element.localName==='p') {
      const text = wordText(element)
      if (startsProtectedSection(text)) protectedSection = true
      if (reservedLabel(text) || /打印|佐证材料/.test(text)) pushManual(layout,'正文',text)
      const inline = !protectedSection && inlineField(text)
      const runs = nodes(element,word,'t')
      if (inline) layout.fields.push({field:inline.field,label:text,where:'正文',
        slot:runs.length===1 && plainParagraph(element)
          ? {...location(mainWord,inline.field.type==='long' ? element : runs[0],
            inline.field.type==='long' ? 'paragraph' : 'wordText','正文'),prefix:inline.prefix} : undefined})
      continue
    }
    if (element.localName!=='tbl') continue
    tableNumber++
    const rows = children(element,word,'tr')
    const recognizable = rows.flatMap(row=>children(row,word,'tc')).filter(cell=>detectField(cellText(cell))).length>=2
    for (const [rowIndex,row] of rows.entries()) {
      const cells = children(row,word,'tc')
      const rowWhere = '表 '+tableNumber+' · 第 '+(rowIndex+1)+' 行'
      const labels = cells.map(cellText)
      if (labels[0] && startsProtectedSection(labels[0])) protectedSection = true
      if (protectedSection || labels.some(text=>/^(紧急联系人|联系人姓名|监护人|家长)/.test(text.trim()))) {
        if (labels[0]?.trim()) pushManual(layout,rowWhere,labels[0])
        continue
      }
      for (const [index,text] of labels.entries()) {
        const where = rowWhere+' · 第 '+(index+1)+' 格'
        if (reservedLabel(text)) {
          pushManual(layout,where,text)
          continue
        }
        const cell = cells[index]
        const nextCell = cells[index+1]
        const field = detectField(text,recognizable && Boolean(wordInput(nextCell,false))) ||
          (wordInput(nextCell,true) ? openField(text,where) : undefined)
        if (field) {
          const long = field.type==='long'
          let target = (!long || canExpand(row)) ? wordInput(nextCell,long) : undefined
          let targetWhere = rowWhere+' · 第 '+(index+2)+' 格'
          if (long && cells.length===1 && !target) {
            const labelRow = wordFullRow(row)
            const nextRow = rows[rowIndex+1]
            const inputRow = wordFullRow(nextRow)
            if (labelRow && inputRow && labelRow.span===inputRow.span && canExpand(nextRow) &&
                !reservedLabel(cellText(inputRow.cell))) {
              target = wordInput(inputRow.cell,true)
              targetWhere = '表 '+tableNumber+' · 第 '+(rowIndex+2)+' 行 · 第 1 格'
            }
          }
          layout.fields.push({field,label:text,where,context:labels.join(' · ').slice(0,500),slot:target
            ? location(mainWord,target,'paragraph',targetWhere) : undefined})
          continue
        }
        const inline = inlineField(text)
        const runs = nodes(cell,word,'t')
        if (inline) layout.fields.push({field:inline.field,label:text,where,slot:runs.length===1 && (inline.field.type!=='long' || canExpand(row)) &&
          children(cell,word,'p').length===1 && plainParagraph(children(cell,word,'p')[0])
          ? {...location(mainWord,inline.field.type==='long' ? children(cell,word,'p')[0] : runs[0],
            inline.field.type==='long' ? 'paragraph' : 'wordText',where),prefix:inline.prefix} : undefined})
      }
    }
  }
  return layout
}

type Coordinate = {column:number; row:number}
function coordinate(address: string): Coordinate | undefined {
  const match = /^([A-Z]{1,3})([1-9]\d{0,6})$/.exec(address)
  if (!match) return
  const column = [...match[1]].reduce((value,char)=>value*26+char.charCodeAt(0)-64,0)
  const row = Number(match[2])
  if (column<=16384 && row<=1048576) return {column,row}
}

function range(reference: string) {
  const [from,to=from] = reference.split(':')
  const start = coordinate(from)
  const end = coordinate(to)
  return start && end ? {start,end} : undefined
}

function inside(value: Coordinate, reference: NonNullable<ReturnType<typeof range>>) {
  return value.row>=reference.start.row && value.row<=reference.end.row &&
    value.column>=reference.start.column && value.column<=reference.end.column
}

function sheetPart(target: string) {
  const path = target.startsWith('/') ? target.slice(1) : 'xl/'+target
  return /^xl\/worksheets\/[A-Za-z0-9_-]+\.xml$/.test(path) ? path : undefined
}

function strings(parts: Package) {
  return parts['xl/sharedStrings.xml'] ? nodes(parse(parts['xl/sharedStrings.xml'],sheet,'sst'),sheet,'si') : []
}

function spreadsheetValue(cell: Element, shared: Element[]) {
  const type = cell.getAttribute('t')
  const value = first(cell,sheet,'v')?.textContent || ''
  const container = type==='s' && /^\d+$/.test(value) ? shared[Number(value)]
    : type==='inlineStr' ? first(cell,sheet,'is') : undefined
  return container ? {
    text:nodes(container,sheet,'t').map(item=>item.textContent).join(''),
    rich:children(container,sheet,'r').length>0,
  } : {text:value,rich:false}
}

function signatureTail(text: string) {
  const mark = /\n[ \t\u3000]*签\s*[名字]\s*[:：]/.exec(text)
  return mark && emptyPlaceholder(text.slice(0,mark.index)) ? text.slice(text.indexOf('\n')) : undefined
}

function sheetLayout(parts: Package): Layout {
  const doc = parse(parts[workbook],sheet,'workbook')
  const relDoc = parse(parts['xl/_rels/workbook.xml.rels'],relationshipNS,'Relationships')
  const shared = strings(parts)
  const styles = parts['xl/styles.xml']
    ? children(first(parse(parts['xl/styles.xml'],sheet,'styleSheet').documentElement,sheet,'cellXfs'),sheet,'xf')
    : []
  const wraps = (cell:Element) => ['1','true'].includes(
    first(styles[Number(cell.getAttribute('s'))],sheet,'alignment')?.getAttribute('wrapText') || '')
  const layout: Layout = {fields:[],manual:[],photoSlot:false}
  const relationships = new Map(nodes(relDoc,relationshipNS,'Relationship').filter(item=>
    item.getAttribute('Type')===rel+'/worksheet' && item.getAttribute('TargetMode')!=='External')
    .map(item=>[item.getAttribute('Id'),sheetPart(item.getAttribute('Target') || '')]))
  for (const entry of nodes(doc,sheet,'sheet').filter(item=>!['hidden','veryHidden'].includes(item.getAttribute('state') || ''))) {
    const name = entry.getAttribute('name') || '工作表'
    const part = relationships.get(entry.getAttributeNS(rel,'id'))
    if (!part || !parts[part]) throw Error('无法核验此工作簿的工作表位置。')
    const doc = parse(parts[part],sheet,'worksheet')
    if (nodes(doc,sheet,'sheetProtection').length) {
      pushManual(layout,name,'工作表已保护，请在 Excel 中核对。')
      continue
    }
    const rows = nodes(doc,sheet,'row')
    if (rows.length>1500 || nodes(doc,sheet,'c').length>12000) throw Error('此工作簿的单元格范围超过本机核对限制。')
    const merges = nodes(doc,sheet,'mergeCell').map(item=>range(item.getAttribute('ref') || ''))
    const restricted = nodes(doc,sheet,'dataValidation').flatMap(item=>(item.getAttribute('sqref') || '').split(/\s+/).map(range))
    if (merges.length>1000 || restricted.length>1000 || [...merges,...restricted].some(item=>!item) ||
        nodes(doc,sheet,'extLst').length) {
      pushManual(layout,name,'工作表含待核对的高级区域或验证规则，请在 Excel 中核对。')
      continue
    }
    const ranges = merges.filter((value):value is NonNullable<typeof value>=>Boolean(value))
    const cells = new Map(rows.map(row=>[Number(row.getAttribute('r')),children(row,sheet,'c').flatMap(element=>{
      const address = element.getAttribute('r') || ''
      const position = coordinate(address)
      return position ? [{element,address,position,...spreadsheetValue(element,shared)}] : []
    })]))
    type Cell = NonNullable<ReturnType<typeof cells.get>>[number]
    const merged = (cell: Cell) => ranges.find(area=>inside(cell.position,area))
    const writable = (cell: Cell | undefined): cell is Cell => {
      if (!cell || cell.rich || !cell.element.hasAttribute('s') || first(cell.element,sheet,'f') ||
          restricted.some(area=>area && inside(cell.position,area))) return false
      const area = merged(cell)
      return !area || (area.start.row===cell.position.row && area.start.column===cell.position.column)
    }
    let protectedSection = false
    for (const [rowIndex,row] of cells) {
      const firstLabel = row.find(item=>item.text.trim())?.text || ''
      if (startsProtectedSection(firstLabel)) protectedSection = true
      const header = row.filter(item=>detectField(item.text)).length>=2
      const beside = (cell: Cell) => {
        const column = merged(cell)?.end.column || cell.position.column
        return row.find(other=>other.position.column===column+1)
      }
      const horizontal = header && !row.some(cell=>detectField(cell.text) && emptyPlaceholder(beside(cell)?.text ?? 'X'))
      const sequence = row.find(cell=>normalizedLabel(cell.text)==='序号')
      const rowAfter = cells.get(rowIndex+1)
      const example = horizontal && sequence && rowAfter?.find(cell=>
        cell.position.column===sequence.position.column && /^(例|示例|样例|范例)$/.test(normalizedLabel(cell.text)))
      const nextNumbered = cells.get(rowIndex+2)
      const dataSequence = example && nextNumbered?.find(cell=>
        cell.position.column===example.position.column && /^[1-9]\d*$/.test(cell.text.trim()) && !first(cell.element,sheet,'f'))
      const dataRow = dataSequence && nextNumbered?.every(cell=>cell===dataSequence ||
        emptyPlaceholder(cell.text) && !first(cell.element,sheet,'f')) ? nextNumbered : undefined
      const heading = dataRow && cells.get(rowIndex-1)?.filter(cell=>cell.text.trim())
      const title = heading?.length===1 ? heading[0].text.trim().slice(0,60) : ''
      const section = dataRow ? {id:part+':'+(rowIndex+2),label:[name,title,'第 '+(rowIndex+2)+' 行'].filter(Boolean).join(' · ')} : undefined
      for (const cell of row) {
        const where = name+' · '+cell.address
        if (protectedSection || reservedLabel(cell.text)) {
          if (reservedLabel(cell.text)) pushManual(layout,where,cell.text)
          continue
        }
        if (first(cell.element,sheet,'f')) continue
        const inline = inlineField(cell.text)
        if (inline) {
          layout.fields.push({field:inline.field,label:cell.text,where,slot:writable(cell)
            ? {...location(part,cell.element,'cell',where),prefix:inline.prefix} : undefined})
          continue
        }
        let target = horizontal ? (example ? dataRow : rowAfter)?.find(other=>other.position.column===cell.position.column) : beside(cell)
        const field = detectField(cell.text,header && Boolean(target && emptyPlaceholder(target.text))) ||
          (writable(target) && emptyPlaceholder(target.text) ? openField(cell.text,where) : undefined)
        if (!field) continue
        if (!horizontal && !target && field.type==='long' && row.filter(item=>item.text.trim()).length===1) {
          const labelArea = merged(cell)
          const below = rowAfter?.find(other=>other.position.column===cell.position.column)
          const inputArea = below && merged(below)
          if (labelArea?.start.row===rowIndex && labelArea.end.row===rowIndex && below && wraps(below.element) &&
              inputArea?.start.row===rowIndex+1 && inputArea.start.column===labelArea.start.column &&
              inputArea.end.column===labelArea.end.column &&
              rowAfter?.every(other=>emptyPlaceholder(other.text) && !first(other.element,sheet,'f'))) target = below
        }
        const blank = target && emptyPlaceholder(target.text)
        const choices = field.id==='type' && target ? checkboxOptions(target.text) : []
        const suffix = field.type==='long' && target ? signatureTail(target.text) : undefined
        const slot = writable(target) && (blank || choices.length || suffix)
          ? location(part,target.element,'cell',name+' · '+target.address) : undefined
        if (slot && choices.length && target) slot.checks = target.text
        if (slot && suffix) slot.suffix = suffix
        layout.fields.push({field:choices.length ? {...field,choices,type:'choice'} : field,
          label:cell.text,where,context:row.map(item=>item.text).join(' · ').slice(0,500),slot,section})
      }
    }
  }
  return layout
}

export function inspectGenericForm(bytes: Uint8Array,name: string): GenericForm {
  const format = /\.docx$/i.test(name) ? 'docx' : 'xlsx'
  const parts = readPackage(bytes)
  if (!(format==='docx' ? parts[mainWord] : parts[workbook] && parts['xl/_rels/workbook.xml.rels'])) {
    throw Error('文件扩展名与 Office 原表结构不匹配。')
  }
  const main = format==='docx' ? mainWord : workbook
  const subtype = format==='docx' ? 'wordprocessingml.document' : 'spreadsheetml.sheet'
  const types = parse(parts['[Content_Types].xml'],contentNS,'Types')
  const packageRels = parse(parts['_rels/.rels'],relationshipNS,'Relationships')
  if (!nodes(types,contentNS,'Override').some(node=>node.getAttribute('PartName')==='/'+main &&
      node.getAttribute('ContentType')==='application/vnd.openxmlformats-officedocument.'+subtype+'.main+xml') ||
      !nodes(packageRels,relationshipNS,'Relationship').some(node=>node.getAttribute('Type')===rel+'/officeDocument' &&
        node.getAttribute('TargetMode')!=='External' && node.getAttribute('Target')?.replace(/^\//,'')===main)) {
    throw Error('无法核验原表的 Office 主文档类型。')
  }
  const layout = format==='docx' ? wordLayout(parts) : sheetLayout(parts)
  const fields = new Map<string,Candidate[]>()
  for (const candidate of layout.fields) {
    const id = candidate.field.id
    const existing = fields.get(id) || []
    existing.push(candidate)
    fields.set(id,existing)
  }
  if (!fields.size) {
    const protectedSheet = layout.manual.find(item=>item.text.startsWith('工作表已保护，') ||
      item.text.startsWith('工作表含待核对的高级区域'))
    throw Error(protectedSheet?.text || '没有找到可核对的字段标签。请打开原件手工填写。')
  }
  if (fields.size>90 || layout.fields.length>180) throw Error('此原表的字段候选超过本机核对限制。')
  const sections = new Map(layout.fields.flatMap(({section,slot})=>section && slot ? [[section.id,section] as const] : []))
  if (sections.size && layout.fields.some(({slot,section})=>slot && !section)) {
    sections.set('other',{id:'other',label:'其他可填写位置'})
  }
  return {name,format,bytes,fields:[...fields].map(([id,candidates])=>({id,candidates})),
    manual:layout.manual,photoSlot:layout.photoSlot,sections:[...sections.values()]}
}

export function suggestedChoice(candidates: Candidate[]) {
  if (candidates.length===1) {
    if (!candidates[0].slot) return 'manual'
    if (!candidates[0].field.id.startsWith('label-')) return '0'
  }
  return ''
}

export function mappingCandidates(form: GenericForm, section?:string) {
  if (!form.sections.length) return form.fields
  return form.fields.flatMap(({id,candidates})=>{
    const selected = candidates.filter(candidate=>(candidate.section?.id || 'other')===section)
    return selected.length ? [{id,candidates:selected}] : []
  })
}

export function mappedFields(mapping: GenericMapping) {
  return mappingCandidates(mapping.form,mapping.section).map(({id,candidates})=>{
    const choice = mapping.choices[id] ?? suggestedChoice(candidates)
    const selected = /^\d+$/.test(choice) ? candidates[Number(choice)] : undefined
    return {...(selected || candidates[0]),slot:selected?.slot,choice:choice==='manual' || selected?.slot ? choice : ''}
  })
}

export function genericScenario(mapping: GenericMapping, physicalPhoto: boolean): Scenario {
  const pastePhoto = mapping.form.manual.some(({text})=>/照片|贴照/.test(text) &&
    /粘贴|贴照|贴.*照片|照片.*贴/.test(text) && !/免贴|无需|不(?:用|要)粘贴/.test(text))
  return {
    id:'imported-template',title:mapping.form.name.replace(/\.(docx|xlsx)$/i,''),school:mapping.school?.trim() || '',source:'',asset:'',
    format:mapping.form.format,provenance:'依据本次导入的原表',
    groups:[{title:'原表字段',fields:mappedFields(mapping).map(item=>({...item.field,export:item.slot ? undefined : false,
      hint:item.where+' · '+(item.slot ? '填入 '+item.slot.where : '位置待核对，列入填写清单'),
    }))}],
    manual:'请核对原表的未识别区域、签字、审核和提交要求。',
    photo:(physicalPhoto || pastePhoto) && mapping.form.photoSlot ? 'physical' : undefined,
  }
}

export function canWriteMapping(mapping: GenericMapping) {
  const items = mappedFields(mapping)
  const positions = items.flatMap(({slot})=>slot ? [slot.part+':'+slot.path.join('/')] : [])
  return items.length>0 && positions.length===items.length && new Set(positions).size===positions.length
}

function setText(element: Element, value: string) {
  element.textContent = value
  element.setAttributeNS(xml,'xml:space','preserve')
}

function insertParagraph(paragraph: Element, value: string) {
  const doc = paragraph.ownerDocument
  const existing = children(paragraph,word,'r')
  const prefix = existing[0]?.prefix || paragraph.prefix
  const tag = (name: string) => prefix ? prefix+':'+name : name
  const run = existing[0] || paragraph.appendChild(doc.createElementNS(word,tag('r')))
  for (const old of nodes(paragraph,word,'t')) old.remove()
  for (const [index,line] of value.split('\n').entries()) {
    if (index) run.appendChild(doc.createElementNS(word,tag('br')))
    const text = run.appendChild(doc.createElementNS(word,tag('t')))
    setText(text,line)
  }
}

function filledValue(slot: Slot, value: string) {
  if (slot.checks) return slot.checks.replace(/([^\s□☐]+)([ \t]*)[□☐]/g,
    (literal,choice:string,spaces:string)=>choice===value ? choice+spaces+'☑' : literal)
  return (slot.prefix ? slot.prefix+' ' : '')+value+(slot.suffix || '')
}

function setSlot(element: Element, slot: Slot, value: string) {
  if (slot.mode==='paragraph') {
    insertParagraph(element,value)
  } else if (slot.mode==='wordText') {
    setText(element,value)
  } else {
    for (const child of Array.from(element.children)) {
      if (child.namespaceURI===sheet && ['v','is'].includes(child.localName)) child.remove()
    }
    const tag = (name:string) => element.prefix ? element.prefix+':'+name : name
    const doc = element.ownerDocument
    const inline = doc.createElementNS(sheet,tag('is'))
    const text = inline.appendChild(doc.createElementNS(sheet,tag('t')))
    setText(text,value)
    element.setAttribute('t','inlineStr')
    element.insertBefore(inline,first(element,sheet,'extLst') || null)
  }
}

function readSlot(element: Element, mode: Mode) {
  if (mode==='paragraph') return Array.from(element.getElementsByTagNameNS(word,'*'))
    .map(node=>node.localName==='t'?node.textContent:node.localName==='br'?'\n':'').join('')
  if (mode==='wordText') return element.textContent
  return first(first(element,sheet,'is'),sheet,'t')?.textContent
}

export function exportGenericForm(mapping: GenericMapping, scenario: Scenario, values: FormValues, stem: string) {
  if (!canWriteMapping(mapping) || validateFilename(stem) || Object.keys(reviewForm(scenario,values,false).errors).length) {
    throw Error('请先补齐字段、核对写入位置和文件名。')
  }
  const parts = readPackage(mapping.form.bytes)
  const format = mapping.form.format
  const fresh = inspectGenericForm(mapping.form.bytes,mapping.form.name)
  const updates = new Map<string,{slot:Slot;value:string}[]>()
  const seen = new Set<string>()
  for (const item of mappedFields({...mapping,form:fresh})) {
    const slot = item.slot
    const value = values[item.field.id]?.trim().replace(/\r\n?/g,'\n')
    if (!value && item.field.optional) continue
    if (!slot || !value || value.length>2000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/.test(value)) {
      throw Error('字段位置失效或内容无法写入，请核对原表。')
    }
    const key = slot.part+':'+slot.path.join('/')
    if (seen.has(key)) throw Error('多个字段指向同一位置，请核对原表。')
    seen.add(key)
    const items = updates.get(slot.part) || []
    items.push({slot,value:filledValue(slot,value)})
    updates.set(slot.part,items)
  }
  const serialize = new XMLSerializer()
  const ns = format==='docx' ? word : sheet
  const root = format==='docx' ? 'document' : 'worksheet'
  for (const [part,items] of updates) {
    const doc = parse(parts[part],ns,root)
    const before = serialize.serializeToString(doc)
    const snapshots = items.map(({slot,value})=>{
      const element = atPath(doc,slot.path)
      const original = element.cloneNode(true)
      setSlot(element,slot,value)
      return {slot,value,original}
    })
    const result = strToU8(serialize.serializeToString(doc))
    const verified = parse(result,ns,root)
    for (const {slot,value,original} of snapshots) {
      const element = atPath(verified,slot.path)
      if (readSlot(element,slot.mode)!==value) throw Error('导出复读与确认值不一致。')
      element.replaceWith(original)
    }
    if (serialize.serializeToString(verified)!==before) throw Error('导出时发现确认位置以外的结构变化。')
    parts[part] = result
  }
  return {filename:officeFilename(format,stem),blob:new Blob([zipSync(parts,{level:6}).slice().buffer],{type:officeMime(format)})}
}
