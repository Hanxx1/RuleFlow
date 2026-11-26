import {ApiError,api} from '../../core/http'
import {requirePrivacyReview} from '../../services/privacyGuard'

export class VaultArchiveUncertain extends Error {
  constructor() {
    super('暂时无法确认是否已保存。请到材料库核对后再决定是否重新保存。')
  }
}

export type VaultArchiveReceipt = {id:string;linkedCase:boolean}
type OfficeFile = {filename:string;blob:Blob}

export async function prepareVaultFormArchive(
  output:OfficeFile,caseId:string|undefined,confirmed:boolean,confirmUnchecked:()=>boolean,
) {
  const file = new File([output.blob],output.filename,{type:output.blob.type})
  const review = await requirePrivacyReview('',[file],'',confirmed)
  if (review.unchecked_sources.length && !confirmUnchecked()) return

  const body = new FormData()
  body.append('file',file)
  body.append('consent','true')
  body.append('name',file.name.trim())
  body.append('category','form')
  body.append('case_ids',JSON.stringify(caseId ? [caseId] : []))
  body.append('task_ids','[]')
  return async ():Promise<VaultArchiveReceipt> => {
    let saved
    try {
      // Keep this explicit write bound to the session used at submission.
      saved = await api('/api/v1/vault/items',{method:'POST',body},false)
    } catch (error) {
      if (error instanceof ApiError && [400,401,403,404,413,415,422].includes(error.status ?? 0)) throw error
      throw new VaultArchiveUncertain()
    }
    if (typeof saved?.id!=='string' || !saved.id || saved.name!==file.name.trim() ||
        saved.category!=='form' || saved.mime!==file.type || saved.size!==file.size ||
        !Array.isArray(saved.case_ids) || saved.case_ids.length!==(caseId ? 1 : 0) ||
        (caseId && saved.case_ids[0]!==caseId) || !Array.isArray(saved.task_ids) || saved.task_ids.length) {
      throw new VaultArchiveUncertain()
    }
    return {id:saved.id,linkedCase:Boolean(caseId)}
  }
}
