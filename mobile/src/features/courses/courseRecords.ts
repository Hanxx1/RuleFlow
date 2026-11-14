import {requirementStates,type CoursePreview,type CourseProfile,type RequirementState} from './courseModel';

// Validates local user records only. Text sources are user declarations, not server EvidenceRef.
function object(value:unknown):Record<string,unknown> {
  if(!value || typeof value!=='object' || Array.isArray(value)) throw Error('课程记录格式无效');
  return value as Record<string,unknown>;
}
function text(value:unknown,max:number,required=false):string {
  if(typeof value!=='string' || value.length>max || required&&!value.trim()) throw Error('课程字段缺失或长度超出限制');
  return value;
}
function list(value:unknown,max:number):unknown[] {
  if(!Array.isArray(value) || value.length>max) throw Error('课程记录数量超出限制或格式无效');
  return value;
}
function profile(value:unknown):CourseProfile {
  const row=object(value);
  return {name:text(row.name,100,true),term:text(row.term,60,true),teacher:text(row.teacher,100),location:text(row.location,200),group:text(row.group,1000)};
}
function requirementValue(value:unknown) {
  const row=object(value),state=row.state as RequirementState;
  if(!requirementStates.includes(state)) throw Error('课程要求状态无效');
  const valueText=text(row.value,2000),source=text(row.source,2000);
  if(state!=='未记录'&&!source.trim()) throw Error('课程要求缺少用户记录的依据');
  if((state==='待核对'||state==='已确认')&&!valueText.trim()) throw Error('课程要求缺少内容');
  if((state==='未记录'||state==='明确无要求')&&valueText.trim()) throw Error('课程要求状态与内容不一致');
  return {state,value:valueText,source};
}
export function validateCourseRecords(value:unknown):CoursePreview[] {
  const ids=new Set<string>();
  return list(value,100).map(input=>{
    const row=object(input),id=text(row.id,200,true);
    if(ids.has(id)) throw Error('课程身份重复，请核对课程记录');
    ids.add(id);
    const requirementIds=new Set<string>();
    const requirements=list(row.requirements,100).map(input=>{
      const item=object(input),id=text(item.id,250,true);
      if(requirementIds.has(id)) throw Error('课程要求身份重复');
      requirementIds.add(id);
      return {id,label:text(item.label,60,true),...requirementValue(item),history:list(item.history,500).map(requirementValue)};
    });
    return {id,...profile(row),profileHistory:list(row.profileHistory,500).map(profile),requirements};
  });
}
