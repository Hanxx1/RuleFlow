import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {createPinia,setActivePinia} from 'pinia';
import {clearSession,setSession} from '../core/http';
import {useDashboardStore} from './dashboard';
vi.mock('../features/cases/store',()=>({useCasesStore:()=>({applyLocalRelevance:async(items:any[])=>{items.forEach(item=>item.relevance='UNKNOWN');return items}})}));

const payload={date:'2026-09-22',timezone:'Asia/Shanghai',total_cases:3,in_progress_cases:1,due_soon_cases:1,completed_cases:2,recent_cases:[{id:'case-1'}],today_tasks:[{id:'task-1',status:'todo'}]};

describe('dashboard store',()=>{
  beforeEach(()=>{setActivePinia(createPinia());setSession('access-token','refresh-token')});
  afterEach(()=>{clearSession();vi.unstubAllGlobals()});

  it('loads owner dashboard data and refreshes after a task mutation',async()=>{
    const fetchMock=vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({data:payload}),{status:200,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({data:{id:'task-1',status:'done'}}),{status:200,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({data:{...payload,today_tasks:[]}}),{status:200,headers:{'Content-Type':'application/json'}}));
    vi.stubGlobal('fetch',fetchMock);
    const store=useDashboardStore();
    await store.load();
    expect(store.data?.total_cases).toBe(3);
    await store.setTask('task-1','done');
    expect(store.data?.today_tasks).toEqual([]);
    expect(fetchMock.mock.calls.map(call=>String(call[0]))).toEqual(expect.arrayContaining([expect.stringContaining('/api/v1/dashboard'),expect.stringContaining('/api/v1/tasks/task-1')]));
  });

  it('does not invent dashboard data without a session',async()=>{
    clearSession();const fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);
    const store=useDashboardStore();
    await expect(store.load()).resolves.toBeNull();
    expect(store.data).toBeNull();expect(fetchMock).not.toHaveBeenCalled();
  });

  it('exposes a retryable error without retaining stale statistics',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const store=useDashboardStore();store.data=payload;
    await expect(store.load()).rejects.toThrow('无法连接在线服务');
    expect(store.data).toBeNull();expect(store.error).toContain('无法连接在线服务');
  });
});
