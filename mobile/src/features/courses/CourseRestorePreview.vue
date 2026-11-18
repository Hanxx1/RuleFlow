<script setup lang="ts">
import {computed,ref,watch,onBeforeUnmount} from 'vue';
import type {Workspace} from '../../services/clientWorkspace';
import {backupSizeLimit,previewCourseRestore,summarizeCourseRestore,type CourseRestorePreview,type RestoreMode} from './courseRestorePreview';
const props=defineProps<{current:Workspace;sample?:boolean}>();
const opened=ref(false),busy=ref(false),error=ref(''),preview=ref<CourseRestorePreview|null>(null),selected=ref<string[]>([]),mode=ref<RestoreMode>('merge'),fileInput=ref<HTMLInputElement|null>(null);
let request=0;
function clear(resetFile=true){request++;busy.value=false;preview.value=null;selected.value=[];error.value='';mode.value='merge';if(resetFile&&fileInput.value)fileInput.value.value=''}
function close(){clear();opened.value=false}
watch(()=>props.current,()=>{clear();opened.value=false},{deep:true,flush:'sync'});
onBeforeUnmount(()=>request++);
const summary=computed(()=>preview.value?summarizeCourseRestore(preview.value,props.current,selected.value,mode.value):null);
async function readFile(event:Event){
  const file=(event.target as HTMLInputElement).files?.[0];clear(false);
  if(!file)return;
  const token=request;busy.value=true;
  try{
    if(file.size>backupSizeLimit)throw Error('备份过大，最多支持 2 MB 的 JSON 文件');
    const raw=await file.text();if(token!==request)return;
    preview.value=previewCourseRestore(raw,props.current);
  }catch(e){if(token===request)error.value=(e as Error).message}
  finally{if(token===request)busy.value=false}
}
</script>

<template>
  <section class="restore panel" aria-label="课程备份预览">
    <button v-if="!opened" type="button" class="button button--secondary" @click="opened=true">预览课程备份</button>
    <template v-else>
      <h2>课程备份恢复预览</h2>
      <p>文件仅在本机读取。本页用于核对，不会恢复、覆盖或删除任何数据。实际恢复尚未开放。</p>
      <p v-if="sample">当前为合成样例预览，使用本机体验身份；不会读取账户资料。</p>
      <label>选择本机资料备份（JSON，最多 2 MB）<input ref="fileInput" type="file" accept=".json,application/json" @change="readFile"></label>
      <p v-if="busy" role="status">正在读取备份…</p><p v-if="error" role="alert" class="error">{{error}}</p>
      <template v-if="preview">
        <p role="status">备份版本 {{preview.backupVersion}} · {{preview.rows.length}} 门课程档案。选择前不会默认勾选任何课程。</p>
        <p>课表记录 {{preview.timetableCount}} 条，本次不合并课表。课程与 Task、日程、知识资料及正式依据的关联尚未核验，均待核对；备份不含服务端原文件。</p>
        <p v-if="!preview.rows.length">此备份没有课程档案。旧课表记录不会自动转换为课程档案。</p>
        <label>预览方式<select v-model="mode"><option value="merge">合并：保留当前冲突项</option><option value="replace">覆盖：仅替换选中的已有课程</option></select></label>
        <p>同名课程不会自动合并。覆盖预期包含该课程的要求和历史，不承诺保留当前较新的历史，请逐项核对。未选择的课程和其他本机资料保持原状。</p>
        <ul class="restore-list">
          <li v-for="row in preview.rows" :key="row.id">
            <label class="selection"><input v-model="selected" type="checkbox" :value="row.id"><span>{{row.incoming.term}} · {{row.incoming.name}} — {{row.status}}</span></label>
            <details><summary>核对课程内容与历史</summary>
              <div v-for="(course,index) in [row.before,row.incoming]" :key="index" class="comparison">
                <h3>{{index===0?'当前本机记录':'备份记录'}}</h3>
                <template v-if="course">
                  <p>{{course.term}} · {{course.name}}<br>教师：{{course.teacher||'未记录'}}；地点：{{course.location||'未记录'}}</p>
                  <p>小组：{{course.group||'未记录'}}；档案历史 {{course.profileHistory.length}} 条</p>
                  <details v-if="course.profileHistory.length"><summary>查看档案旧值</summary><p v-for="(entry,i) in course.profileHistory" :key="i">{{entry.term}} · {{entry.name}} · {{entry.teacher}} · {{entry.location}} · {{entry.group}}</p></details>
                  <article v-for="item in course.requirements" :key="item.id"><h4>{{item.label}} · {{item.state}}</h4><p>{{item.value||'无内容'}}<br>依据：{{item.source||'未记录，待核对'}}</p><details v-if="item.history.length"><summary>要求历史（{{item.history.length}}）</summary><p v-for="(entry,i) in item.history" :key="i">{{entry.state}} · {{entry.value||'无内容'}}<br>依据：{{entry.source||'未记录，待核对'}}</p></details></article>
                </template><p v-else>无对应课程记录</p>
              </div>
            </details>
          </li>
        </ul>
        <p v-if="summary" role="status">仅为预期：新增 {{summary.added}} 门，替换 {{summary.replaced}} 门，保留冲突 {{summary.kept}} 门，相同 {{summary.unchanged}} 门；本机预计共 {{summary.resultCount}} 门。尚未写入。</p>
        <p v-if="summary?.overLimit" role="alert" class="error">预计课程数超过 100 门上限，请减少选择；本次没有写入。</p>
      </template>
      <button type="button" class="button button--secondary" @click="close">取消并关闭预览</button>
    </template>
  </section>
</template>

<style scoped>
.restore{margin:16px 0;overflow-wrap:anywhere}.restore p{line-height:1.7;white-space:pre-wrap}.restore label{display:grid;gap:8px;margin:12px 0}.restore input[type=file],.restore select{width:100%;min-width:0;box-sizing:border-box;font:inherit;padding:10px;border:1px solid #a5bdb3;border-radius:8px;background:white;color:#244a3e}.restore-list{list-style:none;padding:0}.restore-list>li{border-top:1px solid #dce8e2;padding:12px 0}.restore .selection{display:flex;align-items:flex-start}.selection input{flex:none;width:20px;height:20px}.comparison{padding:10px;background:#f2f6f3;margin-top:10px;border-radius:8px}.comparison article{border-top:1px solid #dce8e2}.restore summary{cursor:pointer;padding:8px 0}.error{color:#a12c2c}.restore :focus-visible{outline:3px solid #208c76;outline-offset:3px}
</style>
