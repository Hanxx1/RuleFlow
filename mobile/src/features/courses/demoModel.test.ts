import {describe,it,expect} from 'vitest';
import {createSamples,createCourse,updateCourseProfile,updateRequirement} from './demoModel';
describe('CM-002 presentation boundaries',()=>{
  it('preserves profile revisions, course identity and requirement evidence when editing',()=>{
    const [original,otherTerm]=createSamples();
    const changed=updateCourseProfile(original,{...original,name:' 软件工程实践 ',term:'2027 春季',teacher:' 新教师 ',location:'实验室',group:'用户输入小组'});
    const changedAgain=updateCourseProfile(changed,{...changed,location:'新实验室'});
    expect(changedAgain.id).toBe(original.id);
    expect(changedAgain.name).toBe('软件工程实践');
    expect(changedAgain.profileHistory.map(entry=>[entry.name,entry.location])).toEqual([['软件工程',original.location],['软件工程实践','实验室']]);
    expect(changedAgain.requirements).toEqual(original.requirements);
    expect(original.profileHistory).toEqual([]);
    expect(original.name).toBe('软件工程');
    expect(otherTerm.term).toBe('2026 春季');
  });
  it('rejects an empty profile and does not add a revision for an unchanged save',()=>{
    const [course]=createSamples();
    expect(()=>updateCourseProfile(course,{...course,term:' '})).toThrow('学期');
    expect(()=>updateCourseProfile(course,{...course,name:' '})).toThrow('名称');
    expect(updateCourseProfile(course,{...course,name:` ${course.name} `})).toBe(course);
    expect(course.profileHistory).toEqual([]);
  });
  it('keeps same-name courses in different terms independent',()=>{const [a,b]=createSamples();const changed=updateRequirement(a,a.requirements[0].id,{state:'已确认',value:'用户修正',source:'用户声明'});expect(changed.id).not.toBe(b.id);expect(b.requirements[0].state).toBe('未记录');expect(changed.requirements[0].history[0].value).toBe(a.requirements[0].value);expect(a.requirements[0].value).not.toBe('用户修正')});
  it('keeps complete earlier source history across repeated edits',()=>{let [a]=createSamples();const original=a.requirements[0];a=updateRequirement(a,original.id,{state:'待核对',value:'新说明',source:'用户声明'});a=updateRequirement(a,original.id,{state:'已确认',value:'核对后说明',source:'合成教师原文'});expect(a.requirements[0].history.map(item=>item.source)).toEqual([original.source,'用户声明'])});
  it('never treats missing content as an explicit absence of requirements',()=>{const a=createCourse('new','软件工程','2027 春季');expect(a.requirements.every(r=>r.state==='未记录')).toBe(true);expect(()=>updateRequirement(a,a.requirements[0].id,{state:'明确无要求',value:'',source:''})).toThrow('依据');expect(()=>updateRequirement(a,a.requirements[0].id,{state:'已确认',value:'',source:'用户声明'})).toThrow('内容');expect(()=>updateRequirement(a,a.requirements[0].id,{state:'明确无要求',value:'每周作业',source:'用户声明'})).toThrow('清空')});
  it('rejects an absent identity and creates fresh samples on reopening',()=>{expect(()=>createCourse('id',' ','秋季')).toThrow();const samples=createSamples();samples[0].name='修改';expect(createSamples()[0].name).toBe('软件工程');expect(()=>updateRequirement(samples[0],'absent',{state:'未记录',value:'',source:''})).toThrow('不存在')});
});
