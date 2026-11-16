import {validFact} from './profileFacts';
import {validateCourse,validDay} from './timetable';
import {profileLabels} from './profileLabels';
import {validateCourseRecords} from '../features/courses/courseRecords';
import type {CoursePreview} from '../features/courses/courseModel';
export type Assertion={id:string;field:string;value:any;quote:string;source:'form'|'supplement';scope:string;validUntil:string|null;confirmed:boolean};
export type Course={id:string;title:string;semesterStart:string;semesterEnd:string;weekday:number;startTime:string;endTime:string;startWeek:number;endWeek:number;parity:'all'|'odd'|'even';evidence:{id:string;text:string};cancelledDates:string[]};
export type Workspace={version:3;owner:string;revision:number;form:Record<string,any>;supplement:string;assertions:Assertion[];interests:string[];history:any[];courses:Course[];courseProfiles:CoursePreview[]};
export const emptyWorkspace=(owner:string):Workspace=>({version:3,owner,revision:0,form:{},supplement:'',assertions:[],interests:[],history:[],courses:[],courseProfiles:[]});
export interface WorkspaceStorage{read(owner:string):Promise<any>;write(owner:string,value:Workspace):Promise<void>;remove(owner:string):Promise<void>;commit?(owner:string,revision:number,value:Workspace,canWrite?:()=>boolean):Promise<void>}
function database():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const request=indexedDB.open('zhishi-private-client',2);request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('workspaces'))request.result.createObjectStore('workspaces')};request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(Error('本机资料库无法打开，请检查可用存储空间'))})}
async function operation(owner:string,mode:IDBTransactionMode,perform:(store:IDBObjectStore)=>IDBRequest){const db=await database();return new Promise<any>((resolve,reject)=>{const tx=db.transaction('workspaces',mode);const request=perform(tx.objectStore('workspaces'));let value:any;request.onsuccess=()=>value=request.result;tx.oncomplete=()=>{db.close();resolve(value)};tx.onabort=tx.onerror=()=>{db.close();reject(Error('本机资料保存失败；原有资料未更改'))}})}
export const indexedWorkspace:WorkspaceStorage={read:owner=>operation(owner,'readonly',s=>s.get(owner)),write:async(owner,value)=>{await operation(owner,'readwrite',s=>s.put(JSON.parse(JSON.stringify(value)),owner))},remove:async owner=>{await operation(owner,'readwrite',s=>s.delete(owner))},commit:async(owner,revision,value,canWrite=()=>true)=>{const db=await database();await new Promise<void>((resolve,reject)=>{const tx=db.transaction('workspaces','readwrite'),store=tx.objectStore('workspaces'),request=store.get(owner);let failure='本机资料保存失败';request.onsuccess=()=>{if(!canWrite()){failure='身份已变化，请重新读取课程';tx.abort();return}if((request.result?.revision||0)!==revision){failure='本机资料已被其他页面修改，请重新读取后保存';tx.abort();return}store.put(JSON.parse(JSON.stringify(value)),owner)};tx.oncomplete=()=>{db.close();resolve()};tx.onabort=tx.onerror=()=>{db.close();reject(Error(failure))}})}};
export function validateWorkspace(value:any,owner:string):Workspace{
 if(!value||value.owner!==owner||value.version!==3||!Number.isSafeInteger(value.revision)||value.revision<0)throw Error('资料备份版本或账户不匹配');
 if(typeof value.supplement!=='string'||value.supplement.length>10000||!Array.isArray(value.assertions)||value.assertions.length>100||!Array.isArray(value.courses)||value.courses.length>100||!Array.isArray(value.history)||value.history.length>500||!Array.isArray(value.interests))throw Error('资料格式或数量超出限制');
 for(const [key,val] of Object.entries(value.form||{}))if(!validFact(key,val))throw Error('表单包含无效字段');
 const ids=new Set<string>();for(const a of value.assertions){if(!/^block:client:[A-Za-z0-9-]+$/.test(a.id)||ids.has(a.id)||!validFact(a.field,a.value)||a.value===null||!a.quote?.trim()||a.quote.length>10000||typeof a.confirmed!=='boolean'||!['form','supplement'].includes(a.source)||typeof a.scope!=='string'||a.scope.length>200||a.validUntil!==null&&!validDay(a.validUntil))throw Error('资料卡缺少有效字段或来源');ids.add(a.id)}
 for(const course of value.courses)validateCourse(course);
 if(value.interests.some((v:any)=>!['academic','award','exam','competition','research','career','other'].includes(v)))throw Error('关注分类无效');
 return {version:3,owner,revision:value.revision,form:value.form||{},supplement:value.supplement,assertions:value.assertions,interests:value.interests,history:value.history,courses:value.courses,courseProfiles:validateCourseRecords(value.courseProfiles)};
}
export function upgradeWorkspace(value:any,owner:string):Workspace {
 if(!value || value.owner!==owner || ![1,2,3].includes(value.version))throw Error('资料备份版本或账户不匹配');
 const upgraded=value.version===1?{...value,version:3,courses:value.courses??[],history:value.history??[],interests:value.interests??[],courseProfiles:[]} : value.version===2?{...value,version:3,courseProfiles:[]}:value;
 return validateWorkspace(upgraded,owner);
}
// Read old data without writing it back: the first explicit save migrates inside the revision transaction.
export async function loadWorkspace(owner:string,storage=indexedWorkspace){const value=await storage.read(owner);return value?upgradeWorkspace(value,owner):emptyWorkspace(owner)}
export async function saveWorkspace(value:Workspace,storage=indexedWorkspace,canWrite:()=>boolean=()=>true){if(!canWrite())throw Error('身份已变化，请重新读取课程');const next=validateWorkspace({...value,revision:value.revision+1},value.owner);if(storage.commit)await storage.commit(value.owner,value.revision,next,canWrite);else {if(!canWrite())throw Error('身份已变化，请重新读取课程');await storage.write(value.owner,next)}if(typeof window!=='undefined')window.dispatchEvent(new CustomEvent('zhishi-client-changed',{detail:{owner:value.owner,revision:next.revision}}));return next}
export function parseSupplement(text:string,scope=''):Assertion[]{
 if(text.length>10000)throw Error('补充说明最多10000字');const output:Assertion[]=[];
 const patterns:[string,RegExp,(m:RegExpMatchArray)=>any][]=[['student_type',/我是\s*(本科生|研究生|教师)/g,m=>({'本科生':'undergraduate','研究生':'graduate','教师':'teacher'} as any)[m[1]]],['enrollment_year',/(?:入学年份[：:]?\s*|入学于\s*)(20\d{2})/g,m=>Number(m[1])],['rank_percent',/(?:专业)?排名(?:前|百分比[：:]?)\s*(\d+(?:\.\d+)?)\s*%/g,m=>Number(m[1])],['moral_score',/德育(?:成绩|分)(?:为|[：:])?\s*(\d+(?:\.\d+)?)/g,m=>Number(m[1])],['team_size',/学生队员(?:人数|有)(?:为|[：:])?\s*(\d+)/g,m=>Number(m[1])],['disciplinary_status',/(无纪律处分记录|有纪律处分记录)/g,m=>m[1].startsWith('无')?'clear':'recorded']];
 for(const [field,pattern,value] of patterns)for(const match of text.matchAll(pattern)){const prefix=text.slice(Math.max(0,(match.index||0)-10),match.index);if(/不是|并非|不确定|可能|曾经|以前/.test(prefix))continue;const val=value(match);if(validFact(field,val))output.push({id:'block:client:'+crypto.randomUUID(),field,value:val,quote:match[0],source:'supplement',scope,validUntil:null,confirmed:false})}
 return output;
}
export function formAssertions(facts:Record<string,any>,scope='',validUntil:string|null=null):Assertion[]{return Object.entries(facts).filter(([,v])=>v!==null).map(([field,value])=>{if(!validFact(field,value))throw Error('画像字段无效：'+(profileLabels[field]||field));return {id:'block:client:'+crypto.randomUUID(),field,value,quote:`用户填写 ${profileLabels[field]||field} = ${JSON.stringify(value)}`,source:'form',scope,validUntil,confirmed:true}})}
export function resolvedFacts(workspace:Workspace,scope='',today=new Date(Date.now()+8*3600000).toISOString().slice(0,10)){
 const grouped=new Map<string,Assertion[]>();for(const a of workspace.assertions){if(!a.confirmed||a.scope&&a.scope!==scope||a.validUntil&&a.validUntil<today)continue;grouped.set(a.field,[...(grouped.get(a.field)||[]),a])}
 const facts:Record<string,any>={},evidence:Record<string,Assertion[]>={},conflicts:string[]=[];
 for(const [field,rows] of grouped){if(new Set(rows.map(a=>JSON.stringify(a.value))).size>1){conflicts.push(field);continue}facts[field]=rows[0].value;evidence[field]=rows}
 return {facts,evidence,conflicts};
}
export function exportWorkspace(value:Workspace){return JSON.stringify(validateWorkspace(value,value.owner),null,2)}
export async function importWorkspace(raw:string,owner:string,storage=indexedWorkspace){if(raw.length>2_000_000)throw Error('备份过大');const data=upgradeWorkspace(JSON.parse(raw),owner),current=await loadWorkspace(owner,storage);if(current.courseProfiles.length||data.courseProfiles.length)throw Error('课程恢复预览尚未开放，不能直接恢复或覆盖课程档案');return saveWorkspace({...data,revision:current.revision},storage)}
