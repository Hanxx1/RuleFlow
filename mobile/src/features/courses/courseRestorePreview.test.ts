import {describe,it,expect} from 'vitest';
import {emptyWorkspace,exportWorkspace} from '../../services/clientWorkspace';
import {createCourse,updateRequirement,updateCourseProfile} from './courseModel';
import {backupSizeLimit,previewCourseRestore,summarizeCourseRestore} from './courseRestorePreview';

describe('CM-003 read-only course backup preview',()=>{
  const original=createCourse('fall','线性代数','2026 秋季');
  function setup(){const current=emptyWorkspace('a');current.revision=9;current.courseProfiles=[original];return current}
  it('distinguishes same, new and conflicting stable IDs without merging same names across terms',()=>{
    const current=setup(),backup=setup();
    backup.courseProfiles=[original,createCourse('spring','线性代数','2027 春季')];
    const before=JSON.stringify(current),raw=exportWorkspace(backup),preview=previewCourseRestore(raw,current);
    expect(preview.rows.map(row=>row.status)).toEqual(['相同','新增']);
    expect(preview.revision).toBe(9);expect(JSON.stringify(current)).toBe(before);expect(exportWorkspace(backup)).toBe(raw);
  });
  it('treats source-only and history-only changes as conflicts and retains both versions',()=>{
    const current=setup(),backup=setup();
    backup.courseProfiles=[updateRequirement(original,original.requirements[0].id,{state:'待核对',value:'签到',source:'用户声明'})];
    const preview=previewCourseRestore(exportWorkspace(backup),current);
    expect(preview.rows[0].status).toBe('冲突');expect(preview.rows[0].incoming.requirements[0].history).toHaveLength(1);
    expect(preview.rows[0].before).toEqual(original);
    backup.courseProfiles=[{...original,profileHistory:[{...original,teacher:'旧教师'}]}];
    expect(previewCourseRestore(exportWorkspace(backup),current).rows[0].status).toBe('冲突');
  });
  it('describes merge and selected-only replace without deleting other courses or writing either input',()=>{
    const current=setup(),backup=setup();current.courseProfiles.push(createCourse('local','当前课程','2026 秋季'));
    backup.courseProfiles=[updateCourseProfile(original,{...original,name:'备份旧名称'}),createCourse('new','新增课程','2026 秋季')];
    const raw=exportWorkspace(backup),before=JSON.stringify(current),preview=previewCourseRestore(raw,current);
    expect(summarizeCourseRestore(preview,current,[],'replace')).toMatchObject({added:0,replaced:0,resultCount:2});
    expect(summarizeCourseRestore(preview,current,['fall','new'],'merge')).toMatchObject({added:1,kept:1,replaced:0,resultCount:3});
    expect(summarizeCourseRestore(preview,current,['fall'],'replace')).toMatchObject({added:0,replaced:1,kept:0,resultCount:2});
    expect(JSON.stringify(current)).toBe(before);expect(exportWorkspace(backup)).toBe(raw);
  });
  it('rejects another owner before exposing backup contents or validation details',()=>{
    const secret={...setup(),owner:'b',courseProfiles:[{name:'不应泄露的名称'}]};
    expect(()=>previewCourseRestore(JSON.stringify(secret),setup())).toThrow('账户不匹配');
  });
  it.each([1,2])('previews legacy v%i without manufacturing profiles or migrating storage',version=>{
    const backup:any={...setup(),version};delete backup.courseProfiles;const raw=JSON.stringify(backup);
    expect(previewCourseRestore(raw,setup())).toMatchObject({backupVersion:version,rows:[],timetableCount:0});
    expect(JSON.stringify(backup)).toBe(raw);
  });
  it('rejects corrupt, unsupported, oversized and ambiguous legacy payloads',()=>{
    const current=setup();
    expect(()=>previewCourseRestore('{',current)).toThrow('JSON');
    expect(()=>previewCourseRestore(' '.repeat(backupSizeLimit+1),current)).toThrow('过大');
    expect(()=>previewCourseRestore(JSON.stringify({...setup(),version:4}),current)).toThrow();
    expect(()=>previewCourseRestore(JSON.stringify({...setup(),version:2}),current)).toThrow('旧版');
    const invalid=setup();invalid.courseProfiles=[{...original,requirements:[{...original.requirements[0],state:'明确无要求',source:''}]}];
    expect(()=>previewCourseRestore(JSON.stringify(invalid),current)).toThrow('依据');
  });
  it('rejects duplicate identities instead of silently selecting a winner',()=>{
    const backup=setup();backup.courseProfiles.push(original);
    expect(()=>previewCourseRestore(JSON.stringify(backup),setup())).toThrow('身份重复');
  });
  it('invalidates selections on owner/revision change and refuses missing or duplicate IDs',()=>{
    const current=setup(),preview=previewCourseRestore(exportWorkspace(current),current);
    expect(()=>summarizeCourseRestore(preview,{...current,revision:10},[],'merge')).toThrow('重新预览');
    expect(()=>summarizeCourseRestore(preview,{...current,owner:'b'},[],'merge')).toThrow('重新预览');
    expect(()=>summarizeCourseRestore(preview,current,['missing'],'merge')).toThrow('失效');
    expect(()=>summarizeCourseRestore(preview,current,['fall','fall'],'merge')).toThrow('失效');
  });
  it('reports capacity overflow without dropping current courses or histories',()=>{
    const current=setup();current.courseProfiles=Array.from({length:100},(_,i)=>createCourse(`local-${i}`,'课程','2026 秋季'));
    const preview=previewCourseRestore(exportWorkspace(setup()),current);
    expect(summarizeCourseRestore(preview,current,['fall'],'merge')).toMatchObject({overLimit:true,resultCount:101});
    expect(current.courseProfiles).toHaveLength(100);
  });
});
