import {createHash} from 'node:crypto'
import {beforeEach,describe,expect,it,vi} from 'vitest'
import {ApiError,api,apiBlob} from '../../core/http'
import {readFormContext,type FormContext,type FormContextSource} from '../imports/formContext'
import {preserveAttachmentKeys} from './noticeIntake'
import {defaultNotice,loadSavedNotice,loadSavedOriginal,recheckSavedForm,savedDraftKey,savedNoticeProblem,savedRules} from './savedNotice'
import templateData from './templateData.json'

vi.mock('../../core/http',async importOriginal=>({
  ...await importOriginal<typeof import('../../core/http')>(),api:vi.fn(),apiBlob:vi.fn(),
}))
vi.mock('../imports/formContext',()=>({readFormContext:vi.fn()}))

const raw = Buffer.from(templateData['scholarship.xlsx'],'base64')
const hash = createHash('sha256').update(raw).digest('hex')
const source = (id:string,name:string): FormContextSource => ({
  source_id:id,name,kind:'file',status:'ready',error_code:null,parent_source_id:null,parent_reference_state:'none',
  document_ref:{kind:'document',id:'doc-'+id,revision:0,sha256:hash,name,mime:'application/zip',size:raw.length},
  text_origin:'document_lines',content_hash:hash,text:null,lines:[],
  original:{state:'present',error_code:null},extraction:{state:'empty',error_code:null},
})
const a = source('a','附件1.xlsx')
const b = source('b','附件2.xlsx')
const announcement = (first='附件1申请理由不超过150字',second='附件2申请理由不超过180字'): FormContextSource => ({
  ...source('notice','通知.txt'),text:[first,second].join('\n'),
  extraction:{state:'available',error_code:null},
  lines:[first,second].map((text,index)=>({
    line_id:'line-'+index,document_id:'doc-notice',line_number:10+index,text,page:null,locator:null,
    bbox:null,coordinate_space:null,page_width:null,page_height:null,confidence:null,
  })),
})
const context = (...sources:FormContextSource[]):FormContext => ({
  schema_version:1,batch_id:'batch',batch_revision:5,case_id:null,sources,
})

beforeEach(()=>vi.resetAllMocks())

describe('authenticated inputs',()=>{
  it('passes a fresh batch revision into the existing typed client',async()=>{
    vi.mocked(api).mockResolvedValue({revision:5})
    vi.mocked(readFormContext).mockResolvedValue(context(a,b))
    await expect(loadSavedNotice('batch')).resolves.toEqual(context(a,b))
    expect(api).toHaveBeenCalledWith('/api/v1/import-batches/batch',{cache:'no-store'})
    expect(readFormContext).toHaveBeenCalledWith('batch',5)
  })

  it('retries a stale batch once and refuses an invalid reference without retry',async()=>{
    vi.mocked(api).mockResolvedValueOnce({revision:4}).mockResolvedValueOnce({revision:5})
    vi.mocked(readFormContext).mockRejectedValueOnce(new ApiError('stale','IMPORT_BATCH_STALE',409))
      .mockResolvedValueOnce(context(a))
    await expect(loadSavedNotice('batch')).resolves.toEqual(context(a))
    expect(readFormContext).toHaveBeenNthCalledWith(1,'batch',4)
    expect(readFormContext).toHaveBeenNthCalledWith(2,'batch',5)
    vi.mocked(api).mockResolvedValue({revision:5})
    const invalid = new ApiError('invalid','SOURCE_REFERENCE_INVALID',409)
    vi.mocked(readFormContext).mockRejectedValue(invalid)
    await expect(loadSavedNotice('batch')).rejects.toBe(invalid)
    expect(readFormContext).toHaveBeenCalledTimes(3)
  })

  it('allows a verified Office original when server extraction failed',async()=>{
    vi.mocked(apiBlob).mockResolvedValue(new Blob([new Uint8Array(raw)]))
    await expect(loadSavedOriginal({...a,extraction:{state:'failed',error_code:'parse_failed'}})).resolves.toMatchObject({id:'scholarship'})
    expect(apiBlob).toHaveBeenCalledWith('/api/v1/documents/doc-a/content')
  })

  it('blocks same-size byte changes and never downloads a missing original',async()=>{
    const changed = new Uint8Array(raw)
    changed[changed.length-1]^=1
    vi.mocked(apiBlob).mockResolvedValue(new Blob([changed]))
    await expect(loadSavedOriginal(a)).rejects.toThrow('原件指纹不符')
    await expect(loadSavedOriginal({...b,original:{state:'missing',error_code:'missing'}})).rejects.toThrow('原件已缺失')
    expect(apiBlob).toHaveBeenCalledTimes(1)
  })
})

describe('per-file draft identity and requirements',()=>{
  it('separates same-byte files, versions, reuploads and batches',()=>{
    const sameName = {...b,name:a.name}
    const reupload = {...a,source_id:'a-new'}
    const newVersion = {...a,document_ref:{...a.document_ref!,revision:1}}
    const keys = [a,sameName,reupload,newVersion].map(item=>savedDraftKey('batch',item))
    expect(new Set([...keys,savedDraftKey('other',a)]).size).toBe(5)
  })

  it('preserves the unchanged local file after reordering and refuses ambiguous duplicates',()=>{
    const oldA = {name:'a.xlsx',sha256:'a'}, oldB = {name:'b.xlsx',sha256:'b'}
    const newA = {name:'a.xlsx',sha256:'c'}
    let next = 0
    const create = ()=>`new-${next++}`
    expect(preserveAttachmentKeys([oldA,oldB],['a','b'],[oldB,newA],create)).toEqual(['b','new-0'])
    expect(preserveAttachmentKeys([oldB],['b'],[oldB,oldB],create)).toEqual(['new-1','new-2'])
  })

  it('binds per-table word limits and preserves actual source line identifiers',()=>{
    const notice = announcement(), batch = context(notice,b,a)
    const rules = savedRules(batch,notice,a.source_id,{},[])
    expect(rules.requirements.lengths.reason.max).toBe(150)
    expect(rules.items[0]).toMatchObject({scope:['a'],lineId:'line-0',lineNumber:10})
    expect(savedRules(batch,notice,b.source_id,{},[]).requirements.lengths.reason.max).toBe(180)
  })

  it('keeps formal identifiers when a source row contains line breaks',()=>{
    const original = announcement()
    const notice = {...original,lines:[{...original.lines[0],text:original.text!}]}
    const rules = savedRules(context(notice,a,b),notice,'b',{},[])
    expect(rules.items[1]).toMatchObject({scope:['b'],lineId:'line-0',lineNumber:10})
  })

  it('uses an explicit shared scope without applying it to a new attachment',()=>{
    const notice = announcement('申请理由不超过150字','请提交纸质资料')
    const initial = context(notice,a,b)
    const item = savedRules(initial,notice,'a',{},[]).items[0]
    expect(item.needsScope).toBe(true)
    const scopes = {[item.key]:{applyTo:['a','b'],candidates:['a','b']}}
    const next = context(notice,a,b,source('c','附件3.xlsx'))
    expect(savedRules(next,notice,'b',scopes,[]).requirements.lengths.reason.max).toBe(150)
    expect(savedRules(next,notice,'c',scopes,[]).unresolved).toBe(true)
  })

  it('keeps an unaffected table eligible when its sibling needs a new binding',()=>{
    const notice = announcement()
    const original = savedRules(context(notice,a,b),notice,'b',{},[])
    const scopes = Object.fromEntries(original.items.map(item=>[item.key,{applyTo:item.scope!,candidates:['a','b']}]))
    const reupload = {...a,source_id:'a-new'}
    const latest = context(notice,b,reupload)
    expect(savedRules(latest,notice,'a-new',scopes,[]).unresolved).toBe(true)
    expect(savedRules(latest,notice,'b',scopes,[]).unresolved).toBe(false)
  })

  it('requires an explicit replacement notice after parent removal',()=>{
    const missing = {...a,parent_reference_state:'missing' as const}
    const notice = announcement()
    expect(defaultNotice(context(notice,missing),missing)).toBe('')
    expect(savedNoticeProblem(missing,undefined)).toContain('父来源待核对')
    expect(savedNoticeProblem(missing,notice)).toBe('')
    expect(savedNoticeProblem({...a,parent_reference_state:'valid',parent_source_id:'another'},notice)).toContain('另一份通知')
    expect(defaultNotice(context(a,{...b,extraction:notice.extraction,text:notice.text}),a)).toBe('')
  })
})

describe('export recheck',()=>{
  it('compares actual sources at the same revision and only invalidates affected rules',()=>{
    const notice = announcement(), newer = announcement('附件1申请理由不超过160字')
    const initial = context(notice,a,b), latest = context(newer,b,a,source('c','附件3.xlsx'))
    const recheck = (item:FormContextSource)=>recheckSavedForm(latest,item,savedDraftKey('batch',item),'notice',
      savedRules(initial,notice,item.source_id,{},[]).signature,{},[])
    expect(()=>recheck(a)).toThrow('通知要求或来源已变化')
    expect(recheck(b)).toBe(b)
  })

  it('rejects removed, reuploaded and unavailable originals and a lost parent',()=>{
    const notice = announcement(), bound = {...a,parent_reference_state:'valid' as const,parent_source_id:'notice'}
    const initial = context(notice,bound,b)
    const recheck = (latest:FormContext)=>recheckSavedForm(latest,bound,savedDraftKey('batch',bound),'notice',
      savedRules(initial,notice,'a',{},[]).signature,{},[])
    expect(()=>recheck(context(notice,b,{...a,source_id:'new-a'}))).toThrow('原件已移除或改版')
    expect(()=>recheck(context(notice,{...bound,original:{state:'missing',error_code:'MISSING'}},b))).toThrow('原件已缺失')
    expect(()=>recheck(context({...bound,parent_reference_state:'missing',parent_source_id:null},b))).toThrow('父来源待核对')
  })

  it('revokes confirmation when an unclassified paragraph changes',()=>{
    const notice = {...announcement(),text:'第一个学期'}
    const latest = context({...notice,text:'第二个学期'},a)
    const checked = savedRules(context(notice,a),notice,'a',{},[]).signature
    expect(()=>recheckSavedForm(latest,a,savedDraftKey('batch',a),'notice',checked,{},[]))
      .toThrow('通知要求或来源已变化')
  })
})
