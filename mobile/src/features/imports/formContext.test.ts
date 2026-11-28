import {afterEach,describe,expect,it,vi} from 'vitest';
import {ApiError,clearSession,setSession} from '../../core/http';
import {FormContextInvalid,parseFormContext,readFormContext,type FormContext} from './formContext';

const digest='a'.repeat(64);
function sample():FormContext{return {
  schema_version:1,batch_id:'batch',batch_revision:2,case_id:null,sources:[{
    source_id:'text',name:'通知',kind:'text',status:'ready',error_code:null,
    parent_source_id:null,parent_reference_state:'none',document_ref:null,
    text_origin:'legacy_text',content_hash:digest,text:'Notice',lines:[],
    original:{state:'not_applicable',error_code:null},extraction:{state:'available',error_code:null},
  },{
    source_id:'form',name:'附件',kind:'file',status:'ready',error_code:null,
    parent_source_id:'text',parent_reference_state:'valid',
    document_ref:{kind:'document',id:'doc',revision:1,sha256:digest,name:'form.txt',mime:'text/plain',size:4},
    text_origin:'document_lines',content_hash:digest,text:'Form',
    lines:[{line_id:'line',document_id:'doc',line_number:1,text:'Form',page:null,locator:null,
      bbox:null,coordinate_space:null,page_width:null,page_height:null,confidence:null}],
    original:{state:'present',error_code:null},extraction:{state:'available',error_code:null},
  }],
}}
function response(value:unknown,status=200){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}})}
afterEach(()=>{clearSession();vi.unstubAllGlobals()});

describe('form context reading',()=>{
  it('uses the existing authenticated transport without caching or persisting',async()=>{
    const fetch=vi.fn().mockImplementation(async()=>response({data:sample(),request_id:'synthetic'}));
    vi.stubGlobal('fetch',fetch);setSession('synthetic-access','');
    vi.stubGlobal('localStorage',{setItem:()=>{throw Error('No persistence allowed')}});
    await expect(readFormContext('batch',2)).resolves.toEqual(sample());
    await readFormContext('batch',2);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[0][0]).toMatch(/\/batch\/form-context\?expected_revision=2$/);
    expect(fetch.mock.calls[0][1]).toMatchObject({method:'GET',cache:'no-store',headers:{Authorization:'Bearer synthetic-access'}});
  });
  it('accepts an OCR quadrilateral and rejects mixed or incomplete coordinates',()=>{
    const data=sample(),line=data.sources[1].lines[0]
    line.bbox=[[0,0],[10,0],[10,4],[0,4]]
    expect(parseFormContext(data,'batch',2)).toBe(data)
    line.bbox[0][0]=NaN
    expect(()=>parseFormContext(data,'batch',2)).toThrow(FormContextInvalid)
  })
  it('encodes batch identifiers and checks the response belongs to that batch',async()=>{
    const data={...sample(),batch_id:'a/b ?'};
    const fetch=vi.fn().mockResolvedValue(response({data}));vi.stubGlobal('fetch',fetch);
    await expect(readFormContext('a/b ?',2)).resolves.toEqual(data);
    expect(fetch.mock.calls[0][0]).toContain('/a%2Fb%20%3F/form-context');
  });
  it.each([401,404,409])('preserves HTTP %s and business error codes',async status=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response({detail:{code:'IMPORT_BATCH_STALE'}},status)));
    const error=await readFormContext('batch',2).catch(x=>x);
    expect(error).toBeInstanceOf(ApiError);expect(error.status).toBe(status);expect(error.code).toBe('IMPORT_BATCH_STALE');
  });
  it('propagates network failure without sample fallback',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(readFormContext('batch',2)).rejects.toThrow('无法连接');
  });
  it.each([-1,NaN,Infinity,1.5])('rejects invalid revision %s before any request',async revision=>{
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
    await expect(readFormContext('batch',revision)).rejects.toBeInstanceOf(FormContextInvalid);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('source response validation',()=>{
  it('preserves the payload without mutation, including real nullable coordinates',()=>{
    const value=sample(),before=structuredClone(value);
    expect(parseFormContext(value,'batch',2)).toBe(value);expect(value).toEqual(before);
  });
  it('does not confuse a missing original with retained historical text',()=>{
    const value=sample();value.sources[1].original={state:'missing',error_code:'DOCUMENT_CONTENT_MISSING'};
    expect(parseFormContext(value,'batch',2).sources[1].lines[0].line_id).toBe('line');
  });
  it('accepts failed extraction with a retained original and a separately unacquired file',()=>{
    const value=sample(),source=value.sources[1];source.status='failed';source.text=null;source.lines=[];
    source.extraction={state:'failed',error_code:'DOCUMENT_PARSE_FAILED'};
    expect(parseFormContext(value,'batch',2).sources[1].original.state).toBe('present');
    source.document_ref=null;source.text_origin=null;source.content_hash=null;
    source.original={state:'not_acquired',error_code:null};source.extraction={state:'not_acquired',error_code:null};
    expect(parseFormContext(value,'batch',2).sources[1].document_ref).toBeNull();
  });
  it('accepts an absent parent independently of attachment availability',()=>{
    const value=sample();value.sources[1].parent_reference_state='missing';value.sources[1].parent_source_id=null;
    expect(parseFormContext(value,'batch',2).sources[1].original.state).toBe('present');
  });
  it.each([
    ['schema version',(v:any)=>v.schema_version=2],
    ['batch identity',(v:any)=>v.batch_id='other'],
    ['revision',(v:any)=>v.batch_revision=3],
    ['duplicate source',(v:any)=>v.sources.push(v.sources[0])],
    ['unknown original state',(v:any)=>v.sources[1].original.state='readable'],
    ['unknown extraction state',(v:any)=>v.sources[1].extraction.state='success'],
    ['missing null field',(v:any)=>delete v.sources[0].document_ref],
    ['fake legacy line',(v:any)=>v.sources[0].lines=v.sources[1].lines],
    ['cross-document line',(v:any)=>v.sources[1].lines[0].document_id='other'],
    ['invalid hash',(v:any)=>v.sources[1].document_ref.sha256='bad'],
    ['mismatched hash',(v:any)=>v.sources[1].content_hash='b'.repeat(64)],
    ['changed line text',(v:any)=>v.sources[1].lines[0].text='Other'],
    ['missing parent',(v:any)=>v.sources[1].parent_source_id='unknown'],
    ['self parent',(v:any)=>v.sources[1].parent_source_id='form'],
    ['disclosed deleted parent',(v:any)=>v.sources[1].parent_reference_state='missing'],
    ['invalid coordinates',(v:any)=>v.sources[1].lines[0].bbox=[1,2]],
  ])('rejects %s without embedding private content in errors',(_,mutate)=>{
    const value=sample();mutate(value);
    expect(()=>parseFormContext(value,'batch',2)).toThrow(FormContextInvalid);
    try{parseFormContext(value,'batch',2)}catch(e){expect(String(e)).not.toContain('Notice')}
  });
});
