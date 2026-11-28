export const experienceKinds = {
  award:'获奖', project:'项目', practice:'实践', other:'其他',
} as const

export type ExperienceKind = keyof typeof experienceKinds
export type ExperienceInput = {
  kind:ExperienceKind
  title:string
  month:string
  endMonth:string
  issuer:string
  level:string
  role:string
  contribution:string
  result:string
  hours:string
  proofNote:string
}
export type Experience = ExperienceInput & {id:string;revision:number;confirmed:boolean}
export const experienceLimits = {
  title:120,issuer:120,level:40,role:60,contribution:500,result:300,hours:6,proofNote:200,
} as const

export function emptyExperience(): ExperienceInput {
  return {kind:'award',title:'',month:'',endMonth:'',issuer:'',level:'',role:'',contribution:'',
    result:'',hours:'',proofNote:''}
}

const validMonth = (month:string) => /^[1-9]\d{3}-(0[1-9]|1[0-2])$/.test(month)
const limit = 100

export function experienceSource(entry:Experience) {
  return {id:'block:client:'+entry.id,revision:entry.revision,
    quote:[entry.month,entry.title,entry.issuer].filter(Boolean).join(' · ')}
}

export function normalizeExperience(input:ExperienceInput): ExperienceInput {
  if (!Object.prototype.hasOwnProperty.call(experienceKinds,input.kind)) throw Error('请选择经历类型。')
  const data = {...emptyExperience(),kind:input.kind,month:input.month,endMonth:input.endMonth}
  for (const field of Object.keys(experienceLimits) as (keyof typeof experienceLimits)[]) {
    const value = input[field]?.trim() || ''
    if ([...value].length>experienceLimits[field]) throw Error('有字段超出长度限制，请核对后保存。')
    data[field] = value
  }
  if (!data.title || !validMonth(data.month)) throw Error('请填写名称和有效的开始或获奖年月。')
  if (data.kind==='award') data.endMonth = ''
  if (data.endMonth && (!validMonth(data.endMonth) || data.endMonth<data.month)) {
    throw Error('结束年月须等于或晚于开始年月。')
  }
  if (data.hours && !/^\d{1,4}(\.\d)?$/.test(data.hours)) throw Error('时长请用数字填写，最多保留一位小数。')
  return data
}

export type ExperienceChange = {id:string;revision:number} & (
  {input:ExperienceInput;confirmed:boolean} | {remove:true}
)

export function editExperiences(entries:Experience[],change:ExperienceChange): Experience[] {
  const previous = entries.find(item=>item.id===change.id)
  if ((previous?.revision ?? 0)!==change.revision || ('remove' in change && !previous)) {
    throw Error('这条经历已被修改或删除，请重新读取后操作。')
  }
  if ('remove' in change) return entries.filter(item=>item.id!==change.id)
  if (!previous && entries.length>=limit) throw Error('本机经历已达 100 条，请先整理现有档案。')
  const data = normalizeExperience(change.input)
  if (change.confirmed && data.kind==='award' && !data.issuer) throw Error('确认获奖前请填写颁奖单位。')
  const next = {...data,id:change.id,revision:change.revision+1,confirmed:change.confirmed}
  return [next,...entries.filter(item=>item.id!==change.id)]
}

const storeName = 'accounts'

async function transact(owner:string,write?: (entries:Experience[])=>Experience[]) {
  if (!owner) throw Error('请先登录本账户。')
  const db = await new Promise<IDBDatabase>((resolve,reject)=>{
    const open = indexedDB.open('campusweave-experience-archive',1)
    open.onupgradeneeded = ()=>open.result.createObjectStore(storeName)
    open.onsuccess = ()=>resolve(open.result)
    open.onerror = ()=>reject(Error('本机经历档案无法打开。'))
  })
  try {
    return await new Promise<Experience[]>((resolve,reject)=>{
      const tx = db.transaction(storeName,write?'readwrite':'readonly')
      const store = tx.objectStore(storeName)
      const read = store.get(owner)
      let records:Experience[] = []
      let failure:unknown
      read.onsuccess = ()=>{
        records = read.result ?? []
        if (!write) return
        try {
          records = write(records)
          if (records.length) store.put(records,owner)
          else store.delete(owner)
        } catch (error) {
          failure = error
          tx.abort()
        }
      }
      tx.oncomplete = ()=>resolve(records)
      tx.onabort = ()=>reject(failure || Error('本机经历操作失败，原有档案未更改。'))
    })
  } finally {
    db.close()
  }
}

export const loadExperiences = (owner:string) => transact(owner)
export const clearExperiences = (owner:string) => transact(owner,()=>[])
export const changeExperience = (owner:string,change:ExperienceChange,canWrite:()=>boolean) =>
  transact(owner,entries=>{
    if (!canWrite()) throw Error('账户已变化，请重新核对经历。')
    return editExperiences(entries,change)
  })
