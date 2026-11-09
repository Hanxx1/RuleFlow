// Internal read-only display model, not an API or course identity contract.
import {validDay} from '../../services/timetable';
export type GridItem={id:string;title:string;kind:'course'|'task'|'busy';starts_at:string;ends_at:string;evidence_ids:string[];courseId?:string};
export type Segment={item:GridItem;day:string;start:number;end:number;lane:number;lanes:number;conflict:boolean};
const DAY=86400000;
export const kindLabels={course:'课程',task:'任务',busy:'忙碌'};
export function addDays(day:string,n:number){return new Date(Date.parse(day+'T00:00:00Z')+n*DAY).toISOString().slice(0,10)}
export function weekStart(day:string){return addDays(day,-((new Date(day+'T00:00:00Z').getUTCDay()+6)%7))}
export function dayKey(value:string){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value))}
export function displayInstant(value:string){return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value))}
export function minuteLabel(value:number){return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`}
function instant(value:string){
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/.test(value)||!validDay(value.slice(0,10)))return NaN;
 return Date.parse(value);
}
export function layoutDays(items:GridItem[],days:string[]){
 const errors:string[]=[];
 const valid=items.flatMap(item=>{const start=instant(item.starts_at),end=instant(item.ends_at);if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start){errors.push(`${item.title}：时间数据异常`);return []}return [{item,start,end}]});
 return {errors,days:days.map(day=>{
  const midnight=Date.parse(day+'T00:00:00+08:00');
  const segments:Segment[]=valid.filter(x=>x.start<midnight+DAY&&x.end>midnight).map(x=>({item:x.item,day,start:(Math.max(x.start,midnight)-midnight)/60000,end:(Math.min(x.end,midnight+DAY)-midnight)/60000,lane:0,lanes:1,conflict:false})).sort((a,b)=>a.start-b.start||a.end-b.end||a.item.id.localeCompare(b.item.id));
  let group:Segment[]=[],ends:number[]=[],groupEnd=-1;
  const finish=()=>{for(const s of group){s.lanes=ends.length;s.conflict=group.length>1}};
  for(const s of segments){
   if(s.start>=groupEnd){finish();group=[];ends=[];groupEnd=-1}
   let lane=ends.findIndex(end=>end<=s.start);if(lane<0)lane=ends.length;
   ends[lane]=s.end;s.lane=lane;group.push(s);groupEnd=Math.max(groupEnd,s.end);
  }
  finish();
  return {day,segments,minWidth:Math.max(112,...segments.map(s=>s.lanes*48+8))};
 })};
}
