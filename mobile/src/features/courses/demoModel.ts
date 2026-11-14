// CM-002 presentation-only model. Not a storage schema or shared API contract.
export const requirementStates = ['未记录', '待核对', '明确无要求', '已确认'] as const;
export type RequirementState = typeof requirementStates[number];
export type Requirement = {id:string; label:string; state:RequirementState; value:string; source:string; history:{state:RequirementState; value:string; source:string}[]};
export type CourseProfile = {term:string; name:string; teacher:string; location:string; group:string};
export type CoursePreview = CourseProfile & {id:string; profileHistory:CourseProfile[]; requirements:Requirement[]};
export const commonRequirements = ['考勤','考试与评分','实验','分组','项目','作业'];
export function createCourse(id:string,name:string,term:string):CoursePreview {
  if(!name.trim() || !term.trim()) throw new Error('请填写课程名称和学期。');
  return {id,name:name.trim(),term:term.trim(),teacher:'',location:'',group:'',profileHistory:[],requirements:commonRequirements.map((label,index)=>({id:`${id}-r${index}`,label,state:'未记录',value:'',source:'',history:[]}))};
}
export function updateCourseProfile(course:CoursePreview,input:CourseProfile):CoursePreview {
  if(!input.name.trim() || !input.term.trim()) throw new Error('请填写课程名称和学期。');
  const before:CourseProfile={name:course.name,term:course.term,teacher:course.teacher,location:course.location,group:course.group};
  const next:CourseProfile={name:input.name.trim(),term:input.term.trim(),teacher:input.teacher.trim(),location:input.location.trim(),group:input.group.trim()};
  if((Object.keys(before) as (keyof CourseProfile)[]).every(key=>before[key]===next[key])) return course;
  return {...course,...next,profileHistory:[...course.profileHistory,before]};
}
export function updateRequirement(course:CoursePreview,id:string,input:{state:RequirementState;value:string;source:string}):CoursePreview {
  if(!requirementStates.includes(input.state)) throw new Error('请选择有效的记录状态。');
  if(input.value.length>2000 || input.source.length>2000) throw new Error('要求内容和依据各不能超过 2000 字，请保留原文后分项记录。');
  if(input.state!=='未记录' && !input.source.trim()) throw new Error('请记录依据或注明“用户声明”。');
  if((input.state==='已确认'||input.state==='待核对')&&!input.value.trim()) throw new Error('请填写要求内容。');
  if((input.state==='未记录'||input.state==='明确无要求')&&input.value.trim()) throw new Error('当前状态不能保留要求内容，请清空内容或调整状态。');
  if(!course.requirements.some(item=>item.id===id)) throw new Error('要求已不存在，请重新打开。');
  const current=course.requirements.find(item=>item.id===id)!;
  const next={state:input.state,value:input.value.trim(),source:input.source.trim()};
  if(current.state===next.state && current.value===next.value && current.source===next.source) return course;
  return {...course,requirements:course.requirements.map(item=>item.id!==id?item:{...item,...next,history:[...item.history,{state:item.state,value:item.value,source:item.source}]})};
}
export function createSamples():CoursePreview[] {
  const current=createCourse('sample-current','软件工程','2026 秋季');
  current.teacher='示例教师';current.location='示例教学楼 201';current.group='合成小组：小林（整理资料）、小周（演示）；关联作业待接入';
  current.requirements[0]={...current.requirements[0],state:'已确认',value:'课堂签到，以教师后续通知为准。',source:'合成教师说明第 1 行（仅用于交互演示）'};
  current.requirements[1]={...current.requirements[1],state:'待核对',value:'评分比例尚待教师说明。',source:'合成课程介绍第 2 行（未确认）'};
  current.requirements[2]={...current.requirements[2],state:'明确无要求',source:'合成教师说明第 3 行：本课程无实验要求'};
  return [current,createCourse('sample-previous','软件工程','2026 春季'),createCourse('sample-math','高等数学','2026 秋季')];
}
