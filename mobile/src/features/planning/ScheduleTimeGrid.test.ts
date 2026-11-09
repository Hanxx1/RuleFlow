import {it,expect} from 'vitest';
import {createSSRApp,h} from 'vue';
import {renderToString} from '@vue/server-renderer';
import ScheduleTimeGrid from './ScheduleTimeGrid.vue';
it.each([[[]],[['unknown']],[['known','unknown']]])('marks absent or unresolved evidence in the event and accessible name (%j)',async(ids)=>{
 const html=await renderToString(createSSRApp({render:()=>h(ScheduleTimeGrid,{days:['2026-11-09'],items:[{id:'missing',title:'待查任务',kind:'task',starts_at:'2026-11-09T09:00:00+08:00',ends_at:'2026-11-09T10:00:00+08:00',evidence_ids:ids}],evidence:{known:'synthetic known input'}})}));
 expect(html).toMatch(/aria-label="[^"]*待核对/);expect(html.match(/待核对/g)?.length).toBeGreaterThanOrEqual(3);
});
