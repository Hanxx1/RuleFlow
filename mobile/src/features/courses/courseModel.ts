// Local course profile and requirement editing. No Task, timetable or server Evidence execution.
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
