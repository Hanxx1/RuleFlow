import {Capacitor} from '@capacitor/core';
import {LocalNotifications as notifications} from '@capacitor/local-notifications';
import {Preferences} from '@capacitor/preferences';
import {api} from '../http';

type Item = {id:string;starts_at:string;task_id?:string|null;case_id?:string|null};
type Entry = {owner:string;item:Item;alarm:number;enabled:boolean;paused:boolean};
const key='ruleflow.schedule-reminders.v1';
export const androidReminders=Capacitor.getPlatform()==='android';
let queue:Promise<unknown>=Promise.resolve();

async function entries():Promise<Entry[]> {
  const {value}=await Preferences.get({key});
  return value ? JSON.parse(value) : [];
}
function persist(rows:Entry[]) {return Preferences.set({key,value:JSON.stringify(rows)})}
function serialized(action:()=>Promise<string>):Promise<string> {
  if (!androidReminders) return Promise.resolve('');
  const result=queue.then(action);
  queue=result.catch(()=>{});
  return result.catch(()=>'本机提醒同步失败，请重新打开安排检查。');
}
async function apply(row:Entry,request=false) {
  await notifications.cancel({notifications:[{id:row.alarm}]});
  const at=new Date(row.item.starts_at);
  if (!row.enabled || row.paused) return '';
  if (at.getTime()<=Date.now()) return request?'开始时间已过，本次不会提醒。':'';
  let permission=await notifications.checkPermissions();
  if (request && permission.display.startsWith('prompt')) permission=await notifications.requestPermissions();
  if (permission.display!=='granted') return '通知权限未开启，本次不会提醒。';
  await notifications.schedule({notifications:[{id:row.alarm,title:'日程提醒',body:'请打开应用查看安排。',schedule:{at}}]});
  return '';
}
export async function isReminderEnabled(owner:string,id:string) {
  return androidReminders && (await entries()).some(r=>r.owner===owner && r.item.id===id && r.enabled);
}
export function saveReminder(owner:string,item:Item,enabled:boolean,paused=false) {
  return serialized(async()=>{
    const rows=await entries();
    let row=rows.find(r=>r.owner===owner && r.item.id===item.id);
    if (!row && !enabled) return '';
    if (!row) {
      const used=new Set(rows.map(r=>r.alarm));
      let alarm=1;
      while (used.has(alarm)) alarm++;
      row={owner,item,alarm,enabled,paused}; rows.push(row);
    }
    row.item={id:item.id,starts_at:item.starts_at,task_id:item.task_id,case_id:item.case_id};
    row.enabled=enabled; row.paused=paused;
    await persist(rows);
    const message=await apply(row,enabled);
    if (!enabled) await persist(rows.filter(r=>r!==row));
    return message;
  });
}
export function updateTaskReminders(owner:string,id:string,status:string) {
  return serialized(async()=>{
    const rows=await entries(), linked=rows.filter(r=>r.owner===owner && r.item.task_id===id);
    for (const row of linked) row.paused=['skipped','done'].includes(status);
    await persist(rows);
    let message='';
    for (const row of linked) message=(await apply(row)) || message;
    return message;
  });
}
export function reconcileReminders(owner:string,previous?:string) {
  return serialized(async()=>{
    const rows=await entries();
    for (const row of rows.filter(r=>r.owner===previous && previous!==owner))
      await notifications.cancel({notifications:[{id:row.alarm}]});
    const mine=rows.filter(r=>r.owner===owner);
    if (!mine.length) return '';
    const upcoming:Item[]=await api('/api/v1/schedule?from='+encodeURIComponent(new Date().toISOString()));
    const plans=new Map<string,Map<string,string>>();
    let message='';
    for (const row of mine) {
      const live=upcoming.find(s=>s.id===row.item.id);
      if (live) {
        row.item={id:live.id,starts_at:live.starts_at,task_id:live.task_id,case_id:live.case_id};
        if (live.task_id && live.case_id) {
          if (!plans.has(live.case_id)) {
            const plan=await api('/api/v1/cases/'+encodeURIComponent(live.case_id)+'/plan');
            plans.set(live.case_id,new Map(plan.ordered_tasks.map((t:{id:string;status:string})=>[t.id,t.status])));
          }
          const status=plans.get(live.case_id)?.get(live.task_id);
          row.paused=!status || ['skipped','done'].includes(status);
        } else row.paused=false;
      } else row.enabled=false;
      if (live && Date.parse(live.starts_at)<=Date.now()) row.enabled=false;
      message=(await apply(row)) || message;
    }
    await persist(rows.filter(r=>r.owner!==owner || r.enabled));
    return message;
  });
}
