import {upgradeWorkspace,validateWorkspace,type Workspace} from '../../services/clientWorkspace';
import type {CoursePreview} from './courseModel';

export const backupSizeLimit=2_000_000;
export type RestoreMode='merge'|'replace';
export type CourseRestoreRow={id:string;status:'新增'|'相同'|'冲突';before?:CoursePreview;incoming:CoursePreview};
export type CourseRestorePreview={owner:string;revision:number;backupVersion:number;rows:CourseRestoreRow[];timetableCount:number};

// Read-only projection of the existing backup. No storage, migration writes or execution DTO.
export function previewCourseRestore(raw:string,current:Workspace):CourseRestorePreview {
  if(raw.length>backupSizeLimit)throw Error('备份过大，最多支持 2 MB 的 JSON 文件');
  let input:any;
  try{input=JSON.parse(raw)}catch{throw Error('无法读取备份，请选择有效的 JSON 文件')}
  // Check identity before validating or returning any private backup content.
  if(!input || input.owner!==current.owner)throw Error('备份账户不匹配，无法预览其他身份的资料');
  if(input.version!==3 && input.courseProfiles!==undefined && (!Array.isArray(input.courseProfiles)||input.courseProfiles.length))throw Error('旧版备份包含无法识别的课程档案，请核对备份版本');
  const local=validateWorkspace(current,current.owner),backup=upgradeWorkspace(input,current.owner);
  const localById=new Map(local.courseProfiles.map(course=>[course.id,course]));
  return {owner:current.owner,revision:current.revision,backupVersion:input.version,timetableCount:backup.courses.length,rows:backup.courseProfiles.map(incoming=>{
    const before=localById.get(incoming.id);
    return {id:incoming.id,before,incoming,status:!before?'新增':JSON.stringify(before)===JSON.stringify(incoming)?'相同':'冲突'};
  })};
}

// Describes the selected course scope only; deliberately not a persistence function.
export function summarizeCourseRestore(preview:CourseRestorePreview,current:Workspace,selected:string[],mode:RestoreMode) {
  if(preview.owner!==current.owner || preview.revision!==current.revision)throw Error('本机资料已变化，请重新预览');
  if(mode!=='merge'&&mode!=='replace')throw Error('请选择有效的预览方式');
  const ids=new Set(selected);
  if(ids.size!==selected.length || selected.some(id=>!preview.rows.some(row=>row.id===id)))throw Error('选择的课程已失效，请重新预览');
  const rows=preview.rows.filter(row=>ids.has(row.id));
  const added=rows.filter(row=>row.status==='新增').length;
  const conflicts=rows.filter(row=>row.status==='冲突').length;
  const resultCount=current.courseProfiles.length+added;
  return {added,replaced:mode==='replace'?conflicts:0,kept:mode==='merge'?conflicts:0,unchanged:rows.filter(row=>row.status==='相同').length,resultCount,overLimit:resultCount>100};
}
