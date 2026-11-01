import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {createPinia,setActivePinia} from 'pinia';
import {clearSession,setSession} from '../../core/http';
import {useImportBatchStore} from './batchStore';

const batch={id:'batch-1',title:'混合通知',state:'draft',revision:2,created_at:'now',updated_at:'now',started_at:null,processing_at:null,completed_at:null,source_count:2,successful_source_count:0,failed_source_count:0,sources:[],can_add_sources:true,case_id:null,result:null};

describe('import batch store',()=>{
  beforeEach(()=>{setActivePinia(createPinia());setSession('access-token','refresh-token')});
  afterEach(()=>{clearSession();vi.unstubAllGlobals()});

  it('persists text and URL in one batch before analysis',async()=>{
    const fetchMock=vi.fn(async(input:any,init:any={})=>{
      const url=String(input);
      if(url.endsWith('/api/v1/import-batches')&&init.method==='POST')return new Response(JSON.stringify({data:{...batch,source_count:0}}),{status:200,headers:{'Content-Type':'application/json'}});
      if(url.endsWith('/sources/text'))return new Response(JSON.stringify({data:{id:'text-1',kind:'text'}}),{status:200,headers:{'Content-Type':'application/json'}});
      if(url.endsWith('/sources/url'))return new Response(JSON.stringify({data:{id:'url-1',kind:'url'}}),{status:200,headers:{'Content-Type':'application/json'}});
      return new Response(JSON.stringify({data:batch}),{status:200,headers:{'Content-Type':'application/json'}});
    });
    vi.stubGlobal('fetch',fetchMock);
    const store=useImportBatchStore();
    const saved=await store.saveSources(undefined,{title:'混合通知',text:'通知正文',url:'https://example.com/notice',files:[]});
    expect(saved?.id).toBe('batch-1');
    expect(fetchMock.mock.calls.map(call=>String(call[0]))).toEqual(expect.arrayContaining([expect.stringContaining('/sources/text'),expect.stringContaining('/sources/url')]));
  });

  it('loads a persisted batch and starts idempotent analysis through the batch API',async()=>{
    const queued={...batch,state:'queued',started_at:'now'};
    const fetchMock=vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({data:batch}),{status:200,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({data:queued}),{status:200,headers:{'Content-Type':'application/json'}}));
    vi.stubGlobal('fetch',fetchMock);
    const store=useImportBatchStore();
    await store.load('batch-1');await store.analyze('batch-1');
    expect(store.data?.state).toBe('queued');
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({method:'POST'}));
  });
});
