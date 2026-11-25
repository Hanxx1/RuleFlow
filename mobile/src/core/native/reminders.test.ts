import {beforeEach,expect,it,vi} from 'vitest';
const state=vi.hoisted(()=>({value:'[]',permission:'granted',queue:new Map<number,Date>()}));
vi.mock('@capacitor/core',()=>({Capacitor:{getPlatform:()=>'android'}}));
vi.mock('@capacitor/preferences',()=>({Preferences:{
  get:async()=>({value:state.value}),set:async({value}:{value:string})=>{state.value=value}
}}));
vi.mock('@capacitor/local-notifications',()=>({LocalNotifications:{
  checkPermissions:async()=>({display:state.permission}),
  requestPermissions:async()=>({display:'denied'}),
  cancel:async({notifications}:any)=>{for(const n of notifications)state.queue.delete(n.id)},
  schedule:async({notifications}:any)=>{for(const n of notifications)state.queue.set(n.id,n.schedule.at)}
}}));
vi.mock('../http',()=>({api:vi.fn()}));
import {api} from '../http';
import {saveReminder,updateTaskReminders,reconcileReminders,isReminderEnabled} from './reminders';
const future=(minutes:number)=>new Date(Date.now()+minutes*60000).toISOString();
beforeEach(()=>{state.value='[]';state.permission='granted';state.queue.clear();vi.resetAllMocks()});
it('replaces old times, preserves opted-in state on skip, and cancels idempotently',async()=>{
  const item={id:'s',task_id:'task',starts_at:future(5)};
  await saveReminder('owner',item,true);
  item.starts_at=future(20);
  await saveReminder('owner',item,true);
  expect([...state.queue.values()].map(v=>v.toISOString())).toEqual([item.starts_at]);
  await updateTaskReminders('owner','task','skipped');
  expect(state.queue.size).toBe(0);
  expect(await isReminderEnabled('owner','s')).toBe(true);
  await updateTaskReminders('owner','task','todo');
  expect(state.queue.size).toBe(1);
  await saveReminder('owner',item,false);
  await saveReminder('owner',item,false);
  expect(state.queue.size).toBe(0);
});
it('reports denied permission and keeps the selection for a later authorized restore',async()=>{
  state.permission='prompt';
  const item={id:'s',starts_at:future(10)};
  expect(await saveReminder('owner',item,true)).toContain('通知权限未开启');
  expect(state.queue.size).toBe(0);
  state.permission='granted';
  vi.mocked(api).mockResolvedValue([item]);
  await reconcileReminders('owner');
  expect(state.queue.size).toBe(1);
});
it('restores only live future reminders for the authenticated owner',async()=>{
  const live={id:'live',starts_at:future(10)};
  for(const id of ['live','gone','past'])await saveReminder('a',{...live,id},true);
  await reconcileReminders('','a');
  await saveReminder('b',live,true);
  vi.mocked(api).mockResolvedValue([live,{id:'past',starts_at:future(-10)}]);
  await reconcileReminders('a','b');
  expect(state.queue.size).toBe(1);
  expect(await isReminderEnabled('a','gone')).toBe(false);
});
