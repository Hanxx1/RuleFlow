import type {Course} from './clientWorkspace';
const dayPattern=/^\d{4}-\d{2}-\d{2}$/;
export function validDay(value:string){const instant=Date.parse(value+'T00:00:00Z');return dayPattern.test(value)&&Number.isFinite(instant)&&new Date(instant).toISOString().slice(0,10)===value}
export function validateCourse(c:Course){
 if(!c.id||!c.title?.trim()||c.title.length>200||!validDay(c.semesterStart)||!validDay(c.semesterEnd)||c.semesterStart>c.semesterEnd||(Date.parse(c.semesterEnd)-Date.parse(c.semesterStart))/86400000>366||new Date(c.semesterStart+'T00:00:00Z').getUTCDay()!==1)throw Error('学期开始须为周一，日期和课程名称须有效');
 if(!Number.isInteger(c.weekday)||c.weekday<1||c.weekday>7||!Number.isInteger(c.startWeek)||!Number.isInteger(c.endWeek)||c.startWeek<1||c.endWeek<c.startWeek||c.endWeek>30||!['all','odd','even'].includes(c.parity))throw Error('周次或单双周无效');
 if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(c.startTime)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(c.endTime)||c.startTime>=c.endTime)throw Error('课程起止时间无效');
 if(!/^block:client:[A-Za-z0-9-]+$/.test(c.evidence?.id)||!c.evidence.text?.trim()||!Array.isArray(c.cancelledDates)||c.cancelledDates.some(d=>!validDay(d)))throw Error('课表缺少有效来源');return c;
}
export function expandCourses(courses:Course[],from:string,to:string){
 if(!validDay(from)||!validDay(to)||from>to||(Date.parse(to)-Date.parse(from))/86400000>90)throw Error('课表展开窗口须为90天内');const result:any[]=[];
 for(const input of courses){const c=validateCourse(input);for(let week=c.startWeek;week<=c.endWeek;week++){
  if(c.parity==='odd'&&week%2===0||c.parity==='even'&&week%2===1)continue;
  const date=new Date(c.semesterStart+'T00:00:00Z');date.setUTCDate(date.getUTCDate()+(week-1)*7+c.weekday-1);const day=date.toISOString().slice(0,10);
  if(day<c.semesterStart||day>c.semesterEnd||day<from||day>to||c.cancelledDates.includes(day))continue;
  result.push({id:c.id+':'+day,title:c.title,kind:'course',starts_at:day+'T'+c.startTime+':00+08:00',ends_at:day+'T'+c.endTime+':00+08:00',evidence_ids:[c.evidence.id],quote:c.evidence.text});
 }}return result.sort((a,b)=>a.starts_at.localeCompare(b.starts_at));
}
export function courseConflicts(courses:Course[]){if(!courses.length)return [];const from=courses.map(c=>c.semesterStart).sort()[0],to=courses.map(c=>c.semesterEnd).sort()[courses.length-1];const end=new Date(from+'T00:00:00Z');end.setUTCDate(end.getUTCDate()+90);const blocks=expandCourses(courses,from,to<end.toISOString().slice(0,10)?to:end.toISOString().slice(0,10));return blocks.filter((b,i)=>blocks.slice(0,i).some(a=>a.starts_at<b.ends_at&&b.starts_at<a.ends_at))}
export function parseTimetableText(text:string,semesterStart:string,semesterEnd:string){
 const result:Course[]=[],unparsed:string[]=[];for(const raw of text.split(/\r?\n/).filter(s=>s.trim())){
  const m=raw.match(/^(.{1,100}?)\s+周([一二三四五六日天])\s+(\d{2}:\d{2})\s*[-～]\s*(\d{2}:\d{2})\s+第?(\d+)[-～](\d+)周(?:\s*(单周|双周))?$/);
  if(!m){unparsed.push(raw);continue}const id=crypto.randomUUID();const c:Course={id,title:m[1],semesterStart,semesterEnd,weekday:'一二三四五六日'.indexOf(m[2]==='天'?'日':m[2])+1,startTime:m[3],endTime:m[4],startWeek:Number(m[5]),endWeek:Number(m[6]),parity:m[7]==='单周'?'odd':m[7]==='双周'?'even':'all',evidence:{id:'block:client:'+id,text:raw},cancelledDates:[]};try{validateCourse(c);result.push(c)}catch{unparsed.push(raw)}
 }return {courses:result,unparsed};
}
export function syntheticCourses():Course[]{return parseTimetableText('高等数学 周一 08:00-10:00 第1-18周\n大学英语 周二 10:00-12:00 第1-18周\n实验课 周三 14:00-17:00 第1-18周 单周\n体育 周五 14:00-16:00 第1-18周','2026-09-07','2027-01-10').courses.map(c=>({...c,title:c.title+'（合成示例）',evidence:{...c.evidence,text:'用户选择合成演示课表：'+c.evidence.text}}))}
export function localSchedule(tasks:any[],courses:Course[],from:string,to:string,busy:any[]=[],edges:any[]=[]){
 const occupied=[...expandCourses(courses,from,to),...busy],suggestions:any[]=[],unscheduled:any[]=[];
 for(const task of tasks){if(['done','skipped'].includes(task.status))continue;const predecessors=edges.filter(e=>e.after_task_id===task.id).map(e=>e.before_task_id);if(predecessors.some(id=>!tasks.some(t=>t.id===id&&['done','skipped'].includes(t.status))&&!suggestions.some(b=>b.task_id===id))){unscheduled.push({task_id:task.id,title:task.title,reason:'dependency_blocked'});continue}const readyAt=Math.max(0,...suggestions.filter(b=>predecessors.includes(b.task_id)).map(b=>Date.parse(b.ends_at)));if(!task.evidence_ids?.length){unscheduled.push({task_id:task.id,title:task.title,reason:'missing_evidence'});continue}const duration=task.duration_minutes;if(!Number.isInteger(duration)||duration<=0){unscheduled.push({task_id:task.id,title:task.title,reason:'duration_required'});continue}
  let placed=false;for(let day=new Date(from+'T00:00:00Z');day.toISOString().slice(0,10)<=to&&!placed;day.setUTCDate(day.getUTCDate()+1)){
   const key=day.toISOString().slice(0,10);for(let minute=8*60;minute+duration<=21*60;minute+=30){const start=Date.parse(key+'T00:00:00+08:00')+minute*60000,end=start+duration*60000;
    if(start<readyAt)continue;if(task.deadline&&end>Date.parse(task.deadline.length===10?task.deadline+'T23:59:59+08:00':task.deadline))continue;
    if(occupied.some(b=>Date.parse(b.starts_at)<end&&start<Date.parse(b.ends_at)))continue;
    const block={task_id:task.id,title:task.title,starts_at:new Date(start).toISOString(),ends_at:new Date(end).toISOString(),evidence_ids:task.evidence_ids};suggestions.push(block);occupied.push(block);placed=true;break;
   }}if(!placed)unscheduled.push({task_id:task.id,title:task.title,reason:'no_available_slot'});
 }return {suggestions,unscheduled};
}
