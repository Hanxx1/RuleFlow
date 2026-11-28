import {strFromU8,unzipSync} from 'fflate'
import type {Scenario} from './scenarios'

type Format = Scenario['format']
type Output = {filename:string;blob:Blob}
type VerifiedOutput = Readonly<Output & {sha256?:string}>

const specs = {
  docx:{
    mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    part:'word/document.xml',
  },
  xlsx:{
    mime:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    part:'xl/workbook.xml',
  },
}
const contentTypes = '[Content_Types].xml'

export const officeMime = (format:Format) => specs[format].mime

export function officeFilename(format:Format,stem:string,demo=false) {
  return (demo && !stem.startsWith('演示-') ? '演示-'+stem : stem)+'.'+format
}

async function verifyOutput(format:Format,expectedName:string,output:Output): Promise<VerifiedOutput> {
  const {filename,blob} = output
  const spec = specs[format]
  if (filename!==expectedName || blob.type!==spec.mime || !blob.size) throw Error('导出文件名或文件类型与确认值不一致。')
  const buffer = await blob.arrayBuffer()
  try {
    const parts = unzipSync(new Uint8Array(buffer),{
      filter:entry=>[contentTypes,spec.part,'_rels/.rels'].includes(entry.name),
    })
    const description = parts[contentTypes] && strFromU8(parts[contentTypes])
    if (!description?.includes(spec.mime+'.main+xml') || !description.includes('/'+spec.part) ||
        !parts[spec.part]?.length || !parts['_rels/.rels']?.length) throw Error('missing part')
  } catch {
    throw Error('生成的 Office 文件校验失败，填写内容仍保留，可重试。')
  }
  const digest = await globalThis.crypto?.subtle?.digest('SHA-256',buffer)
  const sha256 = digest && Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('')
  return Object.freeze({filename,blob,sha256})
}

// Hold one output for this confirmation only. A failed write or verification can be retried.
export function createOfficeDelivery(format:Format,expectedName:string,build:()=>Output) {
  let ready:Promise<VerifiedOutput> | undefined
  return () => {
    ready ??= Promise.resolve().then(build).then(output=>verifyOutput(format,expectedName,output)).catch(error=>{
      ready = undefined
      throw error
    })
    return ready
  }
}
