import {it,expect} from 'vitest';
import {createSSRApp,h} from 'vue';
import {renderToString} from '@vue/server-renderer';
import ScheduleTimeGrid from './ScheduleTimeGrid.vue';
it.each([[[]],[['unknown']],[['known','unknown']]])('marks absent or unresolved evidence in the event and accessible name (%j)',async(ids)=>{
 const html=await renderToString(createSSRApp({render:()=>h(ScheduleTimeGrid,{days:['2026-11-09'],items:[{id:'missing',title:'待查任务',kind:'task',starts_at:'2026-11-09T09:00:00+08:00',ends_at:'2026-11-09T10:00:00+08:00',evidence_ids:ids}],evidence:{known:'synthetic known input'}})}));
 expect(html).toMatch(/aria-label="[^"]*待核对/);expect(html.match(/待核对/g)?.length).toBeGreaterThanOrEqual(3);
});
it('shows complete short-slot titles outside the scaled grid, including clipped midnight segments',async()=>{
 const item=(id:string,start:string,end:string)=>({id,title:'完整长标题用于核对课程任务与材料准备',kind:'task' as const,starts_at:start,ends_at:end,evidence_ids:[]});
 const html=await renderToString(createSSRApp({render:()=>h(ScheduleTimeGrid,{days:['2026-11-09'],items:[item('tiny','2026-11-09T12:00:00+08:00','2026-11-09T12:05:00+08:00'),item('midnight','2026-11-08T23:00:00+08:00','2026-11-09T00:10:00+08:00'),item('normal','2026-11-09T14:00:00+08:00','2026-11-09T15:00:00+08:00')],evidence:{}})}));
 expect(html).toContain('aria-label="短时段完整标题"');
 expect(html).toMatch(/data-short-item="tiny"[^>]*>[\s\S]*?完整长标题用于核对课程任务与材料准备/);
 expect(html).toContain('data-short-item="midnight"');
 expect(html).not.toContain('data-short-item="normal"');
 expect(html).toContain('00:00–00:10');
});
it('omits the short-slot list on empty days',async()=>{
 const html=await renderToString(createSSRApp({render:()=>h(ScheduleTimeGrid,{days:['2026-11-09'],items:[],evidence:{}})}));
 expect(html).not.toContain('aria-label="短时段完整标题"');
});
it('groups connected overlaps in week view without swallowing an adjacent event',async()=>{
 const items=[['a','09:00','10:00'],['b','09:30','10:30'],['c','10:00','11:00'],['d','11:00','12:00']].map(([id,start,end])=>({id,title:id,kind:'task' as const,starts_at:`2026-11-09T${start}:00+08:00`,ends_at:`2026-11-09T${end}:00+08:00`,evidence_ids:[]}));
 const render=(days:string[])=>renderToString(createSSRApp({render:()=>h(ScheduleTimeGrid,{days,items,evidence:{}})}));
 const week=await render(['2026-11-09','2026-11-10']);
 expect(week).toContain('data-overlap-count="3"');expect(week).toContain('data-item="d"');expect(week).not.toContain('data-item="a"');
 const day=await render(['2026-11-09']);expect(day).not.toContain('data-overlap-count=');expect(day).toContain('data-item="a"');
});
