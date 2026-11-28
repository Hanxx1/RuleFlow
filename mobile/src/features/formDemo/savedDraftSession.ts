const prefix = 'campusweave:form-draft:v1:'
export const draftIdentity = /^[A-Za-z0-9-]{1,128}$/
export type DraftStorage = Pick<Storage,'length'|'key'|'getItem'|'setItem'|'removeItem'>

function ownerPrefix(owner: string) {
  if (!draftIdentity.test(owner)) throw Error('请使用当前登录账户保存草稿。')
  return prefix+owner+':'
}

export function draftStorageKey(owner: string,batch: string) {
  if (!draftIdentity.test(batch)) throw Error('表单批次无效，请重新打开通知。')
  return ownerPrefix(owner)+batch
}

export function clearOwnerFormDrafts(owner: string,storage: DraftStorage = sessionStorage) {
  const start = ownerPrefix(owner)
  for (let index=storage.length-1;index>=0;index--) {
    const key = storage.key(index)
    if (key?.startsWith(start)) storage.removeItem(key)
  }
}

export function savedDraftReturnPath(batch: unknown) {
  return typeof batch==='string' && draftIdentity.test(batch) ? '/imports/'+batch+'/forms' : '/home'
}
