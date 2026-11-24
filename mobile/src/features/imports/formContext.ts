import {api} from '../../core/http';

export interface SourceLine {
  line_id:string; document_id:string; line_number:number; text:string;
  page:number|null; locator:string|null; bbox:number[]|null;
  coordinate_space:string|null; page_width:number|null; page_height:number|null; confidence:number|null;
}
export interface SourceDocument {
  kind:'document'; id:string; revision:number; sha256:string; name:string; mime:string; size:number;
}
export interface FormContextSource {
  source_id:string; name:string; kind:string; status:string; error_code:string|null;
  parent_source_id:string|null; parent_reference_state:'none'|'valid'|'missing';
  document_ref:SourceDocument|null; text_origin:'document_lines'|'legacy_text'|null;
  content_hash:string|null; text:string|null; lines:SourceLine[];
  original:{state:'present'|'missing'|'not_acquired'|'not_applicable'|'unverified';error_code:string|null};
  extraction:{state:'available'|'failed'|'empty'|'not_acquired';error_code:string|null};
}
export interface FormContext {
  schema_version:1; batch_id:string; batch_revision:number; case_id:string|null; sources:FormContextSource[];
}

export class FormContextInvalid extends Error {
  constructor(){super('来源读取响应无效，请重新读取后核对。');this.name='FormContextInvalid'}
}
const invalid=():never=>{throw new FormContextInvalid()};
const object=(x:unknown):Record<string,any>=>x!==null&&typeof x==='object'&&!Array.isArray(x)?x:invalid();
const string=(x:unknown):x is string=>typeof x==='string';
const id=(x:unknown):x is string=>string(x)&&x.length>0;
const nullableString=(x:unknown)=>x===null||string(x);
const integer=(x:unknown)=>Number.isSafeInteger(x)&&Number(x)>=0;
const nullableNumber=(x:unknown)=>x===null||(typeof x==='number'&&Number.isFinite(x));
const hash=(x:unknown)=>string(x)&&/^[a-f0-9]{64}$/.test(x);

/** Validate without inventing references, repairing a response or retaining it. */
export function parseFormContext(value:unknown,batchId:string,revision:number):FormContext {
  const result=object(value);
  if(result.schema_version!==1||result.batch_id!==batchId||result.batch_revision!==revision||
    !integer(result.batch_revision)||!nullableString(result.case_id)||!Array.isArray(result.sources))invalid();
  const sourceIds=new Set<string>();
  for(const raw of result.sources){
    const lineIds=new Set<string>();
    const source=object(raw),original=object(source.original),extraction=object(source.extraction);
    if(!id(source.source_id)||sourceIds.has(source.source_id)||!string(source.name)||!string(source.kind)||
      !string(source.status)||!nullableString(source.error_code)||!nullableString(original.error_code)||
      !nullableString(extraction.error_code)||!nullableString(source.text)||!Array.isArray(source.lines)||
      !['present','missing','not_acquired','not_applicable','unverified'].includes(original.state)||
      !['available','failed','empty','not_acquired'].includes(extraction.state)||
      !['none','valid','missing'].includes(source.parent_reference_state))invalid();
    sourceIds.add(source.source_id);
    if(source.parent_reference_state==='valid'?!id(source.parent_source_id):source.parent_source_id!==null)invalid();
    if(source.document_ref!==null){
      const doc=object(source.document_ref);
      if(doc.kind!=='document'||!id(doc.id)||!integer(doc.revision)||!hash(doc.sha256)||
        !string(doc.name)||!string(doc.mime)||!integer(doc.size)||source.text_origin!=='document_lines'||
        source.content_hash!==doc.sha256||!['present','missing','unverified'].includes(original.state))invalid();
      let previous=0;
      for(const rawLine of source.lines){
        const line=object(rawLine);
        if(!id(line.line_id)||lineIds.has(line.line_id)||line.document_id!==doc.id||
          !integer(line.line_number)||line.line_number<=previous||!string(line.text)||
          !nullableNumber(line.page)||!nullableString(line.locator)||!nullableString(line.coordinate_space)||
          !nullableNumber(line.page_width)||!nullableNumber(line.page_height)||!nullableNumber(line.confidence)||
          !(line.bbox===null||(Array.isArray(line.bbox)&&line.bbox.length===4&&line.bbox.every((n:unknown)=>typeof n==='number'&&Number.isFinite(n)))))invalid();
        previous=line.line_number;lineIds.add(line.line_id);
      }
      if(source.lines.length){
        if(extraction.state!=='available'||source.text!==source.lines.map((line:SourceLine)=>line.text).join('\n'))invalid();
      }else if(source.text!==null||!['empty','failed'].includes(extraction.state))invalid();
    }else if(source.text_origin==='legacy_text'){
      if(source.kind!=='text'||source.lines.length||original.state!=='not_applicable'||
        (source.text===null?source.content_hash!==null:!hash(source.content_hash))||
        extraction.state!==(source.text?'available':'empty'))invalid();
    }else if(source.text_origin!==null||source.text!==null||source.content_hash!==null||source.lines.length||
      original.state!=='not_acquired'||extraction.state!=='not_acquired')invalid();
  }
  for(const source of result.sources){
    if(source.parent_reference_state==='valid'&&
      (source.parent_source_id===source.source_id||!sourceIds.has(source.parent_source_id)))invalid();
  }
  return result as FormContext;
}

/** Call only on explicit workspace use. No persistence, fallback or export decision. */
export async function readFormContext(batchId:string,expectedRevision:number):Promise<FormContext>{
  if(!id(batchId)||!integer(expectedRevision))throw new FormContextInvalid();
  const result=await api(`/api/v1/import-batches/${encodeURIComponent(batchId)}/form-context?expected_revision=${expectedRevision}`,
    {method:'GET',cache:'no-store'});
  return parseFormContext(result,batchId,expectedRevision);
}
