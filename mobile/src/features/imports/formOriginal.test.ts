import {afterEach,describe,expect,it,vi} from 'vitest';
import {ApiError,clearSession,setSession} from '../../core/http';
import {type FormContext} from './formContext';
import {FormOriginalError,readFormOriginal} from './formOriginal';

const raw='Form';
const digest='2e0e960ab3204127b1dce399c9984c81f52a79f4d85cb0c3afddcfcfe8a2b48c';
function snapshot():FormContext{return {
  schema_version:1,batch_id:'batch',batch_revision:2,case_id:null,sources:[{
    source_id:'form',name:'附件',kind:'file',status:'ready',error_code:null,
    parent_source_id:null,parent_reference_state:'none',
    document_ref:{kind:'document',id:'doc/a ?',revision:1,sha256:digest,name:'form.txt',mime:'text/plain',size:4},
    text_origin:'document_lines',content_hash:digest,text:raw,
    lines:[{line_id:'line',document_id:'doc/a ?',line_number:1,text:raw,page:null,locator:null,
      bbox:null,coordinate_space:null,page_width:null,page_height:null,confidence:null}],
    original:{state:'present',error_code:null},extraction:{state:'available',error_code:null},
  }],
}}
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
function requests(before=snapshot(),content=raw,after=before){
  const fetch=vi.fn().mockResolvedValueOnce(json({data:before}))
    .mockResolvedValueOnce(new Response(content,{headers:{'Cache-Control':'no-store'}}))
    .mockResolvedValueOnce(json({data:after}));
  vi.stubGlobal('fetch',fetch);return fetch;
}
afterEach(()=>{clearSession();vi.unstubAllGlobals();vi.restoreAllMocks()});

describe('verified source original reading',()=>{
  it('authenticates, pins source identity, checks exact bytes and re-reads after download',async()=>{
    const value=snapshot(),before=structuredClone(value),fetch=requests();setSession('synthetic-access','');
    vi.stubGlobal('localStorage',{setItem:()=>{throw Error('No persistence')}});
    const blob=await readFormOriginal(value,'form');
    expect(await blob.text()).toBe(raw);expect(value).toEqual(before);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls[1][0]).toMatch(/\/documents\/doc%2Fa%20%3F\/content$/);
    for(const call of fetch.mock.calls)expect(call[1].headers.Authorization).toBe('Bearer synthetic-access');
    expect(fetch.mock.calls[0][1].cache).toBe('no-store');expect(fetch.mock.calls[2][1].cache).toBe('no-store');
  });
  it.each(['failed','empty'] as const)('reads a retained original with %s extraction',async state=>{
    const value=snapshot(),source=value.sources[0];source.text=null;source.lines=[];source.extraction.state=state;
    requests(value);expect(await (await readFormOriginal(value,'form')).text()).toBe(raw);
  });
  it('can verify actual bytes when storage was previously unverified and the parent was deleted',async()=>{
    const value=snapshot();value.sources[0].original.state='unverified';value.sources[0].parent_reference_state='missing';
    requests(value);await expect(readFormOriginal(value,'form')).resolves.toBeInstanceOf(Blob);
  });
  it.each(['unknown',''])('rejects missing source %s without fetching',async id=>{
    const fetch=requests();await expect(readFormOriginal(snapshot(),id)).rejects.toThrow();expect(fetch).not.toHaveBeenCalled();
  });
  it('does not substitute another source even if its document and bytes match',async()=>{
    const current=snapshot();current.sources[0].source_id='reuploaded';const fetch=requests(current);
    await expect(readFormOriginal(snapshot(),'form')).rejects.toMatchObject({code:'SOURCE_ORIGINAL_UNAVAILABLE'});
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it.each(['missing','not_acquired','not_applicable'] as const)('does not fetch an unavailable %s original',async state=>{
    const value=snapshot(),source=value.sources[0];source.original.state=state;
    if(state!=='missing'){
      source.document_ref=null;source.lines=[];
      source.text_origin=state==='not_applicable'?'legacy_text':null;
      source.kind=state==='not_applicable'?'text':'file';
      source.text=state==='not_applicable'?raw:null;source.content_hash=state==='not_applicable'?digest:null;
      source.extraction.state=state==='not_applicable'?'available':'not_acquired';
    }
    const fetch=requests();
    await expect(readFormOriginal(value,'form')).rejects.toThrow();expect(fetch).not.toHaveBeenCalled();
  });
  it.each(['id','revision','sha256','size','mime','name'] as const)('rejects changed document %s before download',async field=>{
    const current=snapshot(),doc=current.sources[0].document_ref!;
    if(field==='revision'||field==='size')doc[field]+=1;
    else if(field==='sha256'){doc.sha256='b'.repeat(64);current.sources[0].content_hash=doc.sha256}
    else {doc[field]='other';if(field==='id')current.sources[0].lines[0].document_id=doc.id}
    const fetch=requests(current);
    await expect(readFormOriginal(snapshot(),'form')).rejects.toMatchObject({code:'SOURCE_ORIGINAL_CHANGED'});
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it.each(['X','Fake'])('rejects changed bytes %s without exposing contents',async content=>{
    const fetch=requests(snapshot(),content);
    const error=await readFormOriginal(snapshot(),'form').catch(e=>e);
    expect(error).toBeInstanceOf(FormOriginalError);expect(error.code).toBe('SOURCE_ORIGINAL_MISMATCH');
    expect(error.message).not.toContain(content);expect(fetch).toHaveBeenCalledTimes(2);
  });
  it('rejects a source removed during download rather than returning the bytes',async()=>{
    requests(snapshot(),raw,{...snapshot(),sources:[]});
    await expect(readFormOriginal(snapshot(),'form')).rejects.toMatchObject({code:'SOURCE_ORIGINAL_UNAVAILABLE'});
  });
  it('rejects an original replaced while its old bytes were downloading',async()=>{
    const after=snapshot();after.sources[0].document_ref!.revision++;
    requests(snapshot(),raw,after);
    await expect(readFormOriginal(snapshot(),'form')).rejects.toMatchObject({code:'SOURCE_ORIGINAL_CHANGED'});
  });
  it('reuses token rotation when the content request needs authentication renewal',async()=>{
    const fetch=vi.fn().mockResolvedValueOnce(json({data:snapshot()}))
      .mockResolvedValueOnce(json({detail:'expired'},401))
      .mockResolvedValueOnce(json({data:{access_token:'rotated-access',refresh_token:'rotated-refresh'}}))
      .mockResolvedValueOnce(new Response(raw)).mockResolvedValueOnce(json({data:snapshot()}));
    vi.stubGlobal('fetch',fetch);setSession('old-access','synthetic-refresh');
    expect(await (await readFormOriginal(snapshot(),'form')).text()).toBe(raw);
    expect(fetch.mock.calls[2][0]).toMatch(/\/auth\/refresh$/);
    expect(fetch.mock.calls[3][1].headers.Authorization).toBe('Bearer rotated-access');
    expect(fetch.mock.calls[4][1].headers.Authorization).toBe('Bearer rotated-access');
  });
  it('does not confuse an unrelated added source with a changed original',async()=>{
    const current=snapshot();current.sources.push({...structuredClone(current.sources[0]),source_id:'other'});
    requests(current);await expect(readFormOriginal(snapshot(),'form')).resolves.toBeInstanceOf(Blob);
  });
  it('pins the caller reference before awaiting network IO',async()=>{
    const value=snapshot(),fetch=requests();
    const pending=readFormOriginal(value,'form');value.batch_id='mutated';value.sources[0].document_ref!.id='mutated';
    expect(await (await pending).text()).toBe(raw);
    expect(fetch.mock.calls[1][0]).toContain('doc%2Fa%20%3F');expect(fetch.mock.calls[2][0]).toContain('/batch/form-context');
  });
  it.each([0,1,2])('preserves HTTP errors at request %s',async index=>{
    const fetch=requests();fetch.mockReset();
    if(index>0)fetch.mockResolvedValueOnce(json({data:snapshot()}));
    if(index>1)fetch.mockResolvedValueOnce(new Response(raw));
    fetch.mockResolvedValueOnce(json({detail:{code:'SOURCE_REFERENCE_INVALID',message:'拒绝读取'}},409));
    const error=await readFormOriginal(snapshot(),'form').catch(e=>e);
    expect(error).toBeInstanceOf(ApiError);expect(error.code).toBe('SOURCE_REFERENCE_INVALID');expect(error.status).toBe(409);
    expect(fetch).toHaveBeenCalledTimes(index+1);
  });
  it('does not fall back on a network failure',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(readFormOriginal(snapshot(),'form')).rejects.toThrow('无法连接');
  });
  it('fails before downloading if secure digest is unavailable',async()=>{
    const fetch=requests();vi.stubGlobal('crypto',undefined);
    await expect(readFormOriginal(snapshot(),'form')).rejects.toMatchObject({code:'SOURCE_INTEGRITY_UNAVAILABLE'});
    expect(fetch).not.toHaveBeenCalled();
  });
  it('keeps digest implementation errors private',async()=>{
    const fetch=requests();vi.stubGlobal('crypto',{subtle:{digest:()=>Promise.reject(Error('PRIVATE_BYTES'))}});
    const error=await readFormOriginal(snapshot(),'form').catch(e=>e);
    expect(error.code).toBe('SOURCE_INTEGRITY_UNAVAILABLE');expect(error.message).not.toContain('PRIVATE_BYTES');
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
