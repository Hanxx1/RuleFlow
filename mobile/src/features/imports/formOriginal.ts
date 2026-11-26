import {apiBlob} from '../../core/http';
import {FormContextInvalid,parseFormContext,readFormContext,type FormContext,type SourceDocument} from './formContext';

type OriginalErrorCode='SOURCE_ORIGINAL_CHANGED'|'SOURCE_ORIGINAL_UNAVAILABLE'|
  'SOURCE_ORIGINAL_MISMATCH'|'SOURCE_INTEGRITY_UNAVAILABLE';

export class FormOriginalError extends Error {
  constructor(public readonly code:OriginalErrorCode,message:string){
    super(message);this.name='FormOriginalError';
  }
}

function unavailable():never {
  throw new FormOriginalError('SOURCE_ORIGINAL_UNAVAILABLE','当前来源没有可核验的原件，请重新读取后核对。');
}

function requireOriginal(context:FormContext,sourceId:string):SourceDocument {
  const source=context.sources.find(item=>item.source_id===sourceId);
  if(!source?.document_ref||!['present','unverified'].includes(source.original.state))unavailable();
  return source.document_ref;
}

function checkOriginal(context:FormContext,sourceId:string,expected:SourceDocument):void {
  const current=requireOriginal(context,sourceId);
  if(current.id!==expected.id||current.revision!==expected.revision||current.sha256!==expected.sha256||
    current.size!==expected.size||current.mime!==expected.mime||current.name!==expected.name){
    throw new FormOriginalError('SOURCE_ORIGINAL_CHANGED','来源原件版本已变化，请重新读取后核对。');
  }
}

/**
 * Read only on explicit user action. Pin one source, re-read its relationship before and
 * after download, and verify the bytes. This is not a notice/requirements or export check.
 * The existing authenticated content endpoint responds with Cache-Control: no-store.
 */
export async function readFormOriginal(snapshot:FormContext,sourceId:string):Promise<Blob> {
  if(!snapshot||typeof sourceId!=='string'||!sourceId)throw new FormContextInvalid();
  parseFormContext(snapshot,snapshot.batch_id,snapshot.batch_revision);
  // Copy before the first await: caller edits must not change the pinned reference.
  const batchId=snapshot.batch_id,revision=snapshot.batch_revision;
  const expected={...requireOriginal(snapshot,sourceId)};
  const subtle=globalThis.crypto?.subtle;
  if(!subtle){
    throw new FormOriginalError('SOURCE_INTEGRITY_UNAVAILABLE','当前环境无法核验原件，请在支持安全摘要的环境重试。');
  }
  checkOriginal(await readFormContext(batchId,revision),sourceId,expected);
  const blob=await apiBlob(`/api/v1/documents/${encodeURIComponent(expected.id)}/content`);
  if(blob.size!==expected.size){
    throw new FormOriginalError('SOURCE_ORIGINAL_MISMATCH','下载内容与来源原件不一致，请重新读取后核对。');
  }
  let digest:ArrayBuffer;
  try{digest=await subtle.digest('SHA-256',await blob.arrayBuffer())}
  catch{
    throw new FormOriginalError('SOURCE_INTEGRITY_UNAVAILABLE','原件摘要核验失败，请重试。');
  }
  const hash=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
  if(hash!==expected.sha256){
    throw new FormOriginalError('SOURCE_ORIGINAL_MISMATCH','下载内容与来源原件不一致，请重新读取后核对。');
  }
  checkOriginal(await readFormContext(batchId,revision),sourceId,expected);
  return blob;
}
