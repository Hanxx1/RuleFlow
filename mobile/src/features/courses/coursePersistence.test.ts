import {describe,it,expect,vi} from 'vitest';
import {createCourse,updateCourseProfile,updateRequirement} from './courseModel';
import {validateCourseRecords} from './courseRecords';
import {emptyWorkspace,loadWorkspace,saveWorkspace,exportWorkspace,importWorkspace,type Workspace,type WorkspaceStorage} from '../../services/clientWorkspace';
import {syntheticCourses} from '../../services/timetable';

const copy=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
function memory(initial:any) {
  const records=new Map<string,any>(initial?[[initial.owner,copy(initial)]]:[]);
  const storage:WorkspaceStorage={
    read:async owner=>copy(records.get(owner)??null),
    write:vi.fn(async(owner,value)=>{records.set(owner,copy(value))}),
    remove:async owner=>{records.delete(owner)},
    commit:vi.fn(async(owner,revision,value,canWrite=()=>true)=>{
      if(!canWrite())throw Error('身份已变化');
      if((records.get(owner)?.revision??0)!==revision)throw Error('已被其他页面修改');
      records.set(owner,copy(value));
    }),
  };
  return {records,storage};
}
describe('local course persistence',()=>{
  it.each([1,2])('reads v%i without mutating the old record and migrates on explicit save',async version=>{
    const legacy:any={...emptyWorkspace('a'),version,revision:4,courses:syntheticCourses()};delete legacy.courseProfiles;
    const original=copy(legacy),{records,storage}=memory(legacy);
    const current=await loadWorkspace('a',storage);
    expect(current).toMatchObject({version:3,revision:4,courseProfiles:[]});
    expect(current.courses).toEqual(legacy.courses);expect(records.get('a')).toEqual(original);
    expect(storage.write).not.toHaveBeenCalled();expect(storage.commit).not.toHaveBeenCalled();
    current.courseProfiles=[createCourse('course-a','软件工程','2026 秋季')];
    await saveWorkspace(current,storage);
    expect(records.get('a')).toMatchObject({version:3,revision:5,courseProfiles:[{id:'course-a'}]});
    expect(records.get('a').courses).toEqual(original.courses);
  });
  it('preserves course identity, profile and requirement history across a close and reopen',async()=>{
    const {storage}=memory(null);let value=emptyWorkspace('a');
    const original=createCourse('fall','软件工程','2026 秋季');
    let course=updateCourseProfile(original,{...original,teacher:'用户填写教师'});
    course=updateRequirement(course,course.requirements[0].id,{state:'待核对',value:'用户记录：课堂签到',source:'用户声明：课堂笔记'});
    value.courseProfiles=[course,createCourse('spring','软件工程','2026 春季')];
    await saveWorkspace(value,storage);const reopened=await loadWorkspace('a',storage);
    expect(reopened.courseProfiles).toEqual(value.courseProfiles);
    expect(reopened.courseProfiles[0].profileHistory[0].teacher).toBe('');
    expect(reopened.courseProfiles[0].requirements[0].history[0].state).toBe('未记录');
    reopened.courseProfiles[0].name='仅改内存';
    expect((await loadWorkspace('a',storage)).courseProfiles[0].name).toBe('软件工程');
  });
  it('keeps a stale course edit from overwriting another page and retains the caller draft',async()=>{
    const {records,storage}=memory(emptyWorkspace('a'));
    const coursePage=await loadWorkspace('a',storage),profilePage=await loadWorkspace('a',storage);
    profilePage.supplement='另一页面刚保存的说明';await saveWorkspace(profilePage,storage);
    coursePage.courseProfiles=[createCourse('draft','保留输入','2026 秋季')];
    await expect(saveWorkspace(coursePage,storage)).rejects.toThrow('其他页面');
    expect(records.get('a').supplement).toBe(profilePage.supplement);
    expect(records.get('a').courseProfiles).toEqual([]);expect(coursePage.courseProfiles[0].name).toBe('保留输入');
  });
  it('rejects malformed requirements before any storage write',async()=>{
    const {records,storage}=memory(emptyWorkspace('a')),value=await loadWorkspace('a',storage);
    value.courseProfiles=[createCourse('bad','课程','2026 秋季')];
    value.courseProfiles[0].requirements[0].state='明确无要求';
    await expect(saveWorkspace(value,storage)).rejects.toThrow('依据');
    expect(records.get('a').revision).toBe(0);expect(storage.commit).not.toHaveBeenCalled();
  });
  it('does not borrow another owner data and rejects a mismatched legacy owner without writing',async()=>{
    const {records,storage}=memory({...emptyWorkspace('a'),version:2});
    expect((await loadWorkspace('b',storage)).courseProfiles).toEqual([]);
    const dishonest={...storage,read:async()=>records.get('a')};
    await expect(loadWorkspace('b',dishonest)).rejects.toThrow('账户');expect(storage.write).not.toHaveBeenCalled();
  });
  it('prevents a pending course save after its identity is revoked',async()=>{
    const {records,storage}=memory(emptyWorkspace('a'));let allowed=true;
    const commit=storage.commit!;
    storage.commit=async(...args)=>{allowed=false;await storage.remove('a');return commit(...args)};
    await expect(saveWorkspace(emptyWorkspace('a'),storage,()=>allowed)).rejects.toThrow('身份');
    expect(records.has('a')).toBe(false);
  });
  it('rolls back all course changes on a storage failure',async()=>{
    const {records,storage}=memory(emptyWorkspace('a')),value=await loadWorkspace('a',storage);
    value.courseProfiles=[createCourse('new','课程','2026 秋季')];storage.commit=async()=>{throw Error('磁盘写入失败')};
    await expect(saveWorkspace(value,storage)).rejects.toThrow('写入失败');
    expect(records.get('a')).toEqual(emptyWorkspace('a'));
  });
  it('exports histories but blocks course restore until impact preview is implemented',async()=>{
    const value=emptyWorkspace('a');value.courseProfiles=[createCourse('saved','课程','2026 秋季')];
    const backup=exportWorkspace(value);expect(JSON.parse(backup).courseProfiles).toEqual(value.courseProfiles);
    const {storage}=memory(value);
    await expect(importWorkspace(JSON.stringify({...emptyWorkspace('a'),version:2}), 'a',storage)).rejects.toThrow('预览');
    await expect(importWorkspace(backup,'a',memory(null).storage)).rejects.toThrow('预览');
    await expect(importWorkspace(backup,'b',storage)).rejects.toThrow('账户');
    expect(storage.commit).not.toHaveBeenCalled();
  });
  it('keeps old non-course backup imports working and rejects unsupported versions',async()=>{
    const {storage}=memory(null),legacy:any={...emptyWorkspace('a'),version:2,supplement:'旧说明'};delete legacy.courseProfiles;
    expect(await importWorkspace(JSON.stringify(legacy),'a',storage)).toMatchObject({version:3,supplement:'旧说明',courseProfiles:[]});
    await expect(loadWorkspace('a',{...storage,read:async()=>({...legacy,version:99})})).rejects.toThrow('版本');
  });
  it('rejects duplicate course identities and malformed historic states without modifying input',()=>{
    const course=createCourse('a','课程','2026 秋季'),before=copy(course);
    expect(()=>validateCourseRecords([course,course])).toThrow('身份重复');
    const invalid:any=copy(course);invalid.requirements[0].history=[{state:'明确无要求',value:'每周签到',source:'用户声明'}];
    expect(()=>validateCourseRecords([invalid])).toThrow('不一致');
    expect(course).toEqual(before);
  });
});
