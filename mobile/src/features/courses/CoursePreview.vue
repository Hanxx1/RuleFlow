<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref,watch} from 'vue';
import {RouterLink} from 'vue-router';
import {commonRequirements,createCourse,requirementStates,updateCourseProfile,updateRequirement,type RequirementState,type CoursePreview} from './courseModel';
import {createSamples} from './demoModel';
import {useAccountStore} from '../../stores/account';
import {loadWorkspace,saveWorkspace,indexedWorkspace,type Workspace} from '../../services/clientWorkspace';
const props=withDefaults(defineProps<{integrated?:boolean}>(),{integrated:false});
const account=props.integrated?useAccountStore():null;
const owner=computed(()=>account?.user?.id||'offline');
const workspace=ref<Workspace|null>(null),loading=ref(props.integrated),saving=ref(false),changedElsewhere=ref(false);
let generation=0,alive=true,originalTitle='';
const courses=ref(props.integrated?[]:createSamples()),selected=ref(''),term=ref('全部学期'),tab=ref('总览'),error=ref(''),message=ref('');
const course=computed(()=>courses.value.find(item=>item.id===selected.value));
const terms=computed(()=>[...new Set(courses.value.map(item=>item.term))]);
const visible=computed(()=>courses.value.filter(item=>term.value==='全部学期'||item.term===term.value));
const creating=ref(false),editing=ref(false),editingRequirement=ref('');
const profile=ref({name:'',term:'',teacher:'',location:'',group:''});
const requirement=ref({state:'未记录' as RequirementState,value:'',source:''}),custom=ref('');
const requirementMode=ref<'quick'|'full'>('quick');
async function reload(preserveDraft=false){
  if(!props.integrated)return;
  const request=++generation,identity=owner.value;loading.value=true;error.value='';
  if(!preserveDraft){courses.value=[];workspace.value=null;editing.value=false;creating.value=false;editingRequirement.value='';custom.value='';profile.value={name:'',term:'',teacher:'',location:'',group:''};requirement.value={state:'未记录',value:'',source:''};message.value=''}
  try{const loaded=await loadWorkspace(identity);if(!alive||request!==generation||identity!==owner.value)return;workspace.value=loaded;courses.value=loaded.courseProfiles;changedElsewhere.value=false;if(preserveDraft)message.value='已读取最新记录，本次输入仍保留；请核对后再保存。'}
  catch(e){if(request===generation){workspace.value=null;error.value=(e as Error).message}}
  finally{if(request===generation)loading.value=false}
}
watch(owner,()=>{selected.value='';term.value='全部学期';void reload()}, {flush:'sync'});
onMounted(()=>{if(props.integrated){originalTitle=document.title;document.title='我的课程 · 有绪 CampusWeave'}void reload();window.addEventListener('zhishi-client-changed',onWorkspaceChange)});
onBeforeUnmount(()=>{alive=false;generation++;if(props.integrated&&document.title==='我的课程 · 有绪 CampusWeave')document.title=originalTitle;window.removeEventListener('zhishi-client-changed',onWorkspaceChange)});
function onWorkspaceChange(event:Event){if(!props.integrated||saving.value)return;const detail=(event as CustomEvent).detail;if(!detail || detail.owner===owner.value)changedElsewhere.value=true}
async function persistCourses(next:CoursePreview[]){
  if(!props.integrated){courses.value=next;return}
  if(!workspace.value||loading.value)throw Error('课程尚未读取，请先重新读取');
  const request=generation,identity=owner.value;
  const saved=await saveWorkspace({...workspace.value,courseProfiles:next},indexedWorkspace,()=>alive&&request===generation&&identity===owner.value);
  if(!alive||request!==generation||identity!==owner.value)throw Error('身份已变化，请重新读取课程');
  workspace.value=saved;courses.value=saved.courseProfiles;changedElsewhere.value=false;
}
function open(id:string){if(saving.value)return;selected.value=id;tab.value='总览';error.value='';message.value='';editing.value=false;editingRequirement.value='';creating.value=false}
function startProfile(isNew=false){creating.value=isNew;editing.value=true;error.value='';profile.value=isNew?{name:'',term:'',teacher:'',location:'',group:''}:{...course.value!}}
async function saveProfile(){if(saving.value)return;const request=generation;saving.value=true;try{const data=creating.value?{...createCourse(crypto.randomUUID(),profile.value.name,profile.value.term),teacher:profile.value.teacher.trim(),location:profile.value.location.trim(),group:profile.value.group.trim()}:updateCourseProfile(course.value!,profile.value);await persistCourses(creating.value?[...courses.value,data]:courses.value.map(item=>item.id===data.id?data:item));if(request!==generation)return;selected.value=data.id;editing.value=false;creating.value=false;term.value='全部学期';message.value=props.integrated?'课程档案已保存在当前身份的本机资料库。':'样例已更新；刷新页面将恢复初始内容。';error.value=''}catch(e){if(request===generation)error.value=(e as Error).message}finally{saving.value=false}}
function startRequirement(id:string){const item=course.value!.requirements.find(r=>r.id===id)!;requirement.value={state:item.state,value:item.value,source:item.source};requirementMode.value='quick';editingRequirement.value=id;error.value='';message.value=''}
async function saveRequirement(){if(saving.value)return;const request=generation;saving.value=true;try{const before=course.value!;const updated=updateRequirement(before,editingRequirement.value,requirement.value);if(updated!==before)await persistCourses(courses.value.map(item=>item.id===updated.id?updated:item));if(request!==generation)return;editingRequirement.value='';error.value='';message.value=updated===before?'内容未改变，未新增历史记录。':props.integrated?'要求及旧值历史已一同保存在本机。':'本次人工修改和原记录已分别保留在样例历史中。'}catch(e){if(request===generation)error.value=(e as Error).message}finally{saving.value=false}}
async function addCustom(){if(saving.value)return;const label=custom.value.trim();if(!label){error.value='请填写自定义字段名称。';return}if(course.value!.requirements.some(item=>item.label===label)){error.value='本课程已有同名要求。';return}const request=generation;saving.value=true;try{const updated={...course.value!,requirements:[...course.value!.requirements,{id:crypto.randomUUID(),label,state:'未记录' as RequirementState,value:'',source:'',history:[]}]};await persistCourses(courses.value.map(item=>item.id===updated.id?updated:item));if(request===generation){custom.value='';error.value=''}}catch(e){if(request===generation)error.value=(e as Error).message}finally{saving.value=false}}
</script>

<template>
  <div class="page courses-preview">
    <RouterLink v-if="integrated" class="text-link" to="/home">← 返回工作台</RouterLink>
    <header><p class="eyebrow">有绪 CampusWeave · 繁事有绪，办事有方。</p><h1>我的课程</h1><p>按学期整理课程，让每条要求都有依据。</p></header>
    <aside class="preview-note"><template v-if="integrated"><strong>{{account?.signedIn?'当前账户的本机课程':'本机体验课程，与登录账户隔离'}}</strong><p>主动保存后可刷新或重开；课程不会自动上传。依据文字为用户记录，外部来源仍待核对。退出登录会清除该账户的本机课程，请先到个人画像导出本机备份。</p><p>本期仅支持备份导出，课程恢复预览尚未接入。任务、资料和课表时间尚未关联。</p></template><template v-else><strong>课程交互样例</strong><p>全部为合成数据，修改仅在本页内存中生效，刷新后重置。不会读取或保存账户、课表、任务和资料。</p></template></aside>
    <p v-if="loading" role="status">正在读取本机课程…</p>
    <div v-if="integrated" class="actions"><p v-if="changedElsewhere">本机资料可能已变化，保存前请重新读取并核对。</p><button class="button button--secondary" :disabled="loading||saving" @click="reload(true)">读取最新记录，保留草稿</button></div>
    <p v-if="message" role="status">{{message}}</p><p v-if="error" role="alert" class="error">{{error}}</p>
    <fieldset :disabled="loading||saving||(integrated&&!workspace)" class="course-content">
    <form v-if="editing" class="panel editor" @submit.prevent="saveProfile">
      <h2>{{creating?(integrated?'新增课程':'新增课程样例'):'编辑课程档案'}}</h2>
      <label>课程名称<input v-model="profile.name" maxlength="100" required></label><label>学期<input v-model="profile.term" placeholder="例如：2026 秋季" maxlength="60" required></label>
      <label>教师<input v-model="profile.teacher" maxlength="100"></label><label>上课地点<input v-model="profile.location" maxlength="200"></label>
      <label>小组成员与分工<textarea v-model="profile.group" maxlength="1000" placeholder="记录成员与分工；关联作业待接入"></textarea></label>
      <div class="actions"><button class="button" type="submit">{{integrated?'保存课程':'应用到样例'}}</button><button class="button button--secondary" type="button" @click="editing=false;creating=false;error=''">取消编辑</button></div>
    </form>
    <template v-else-if="!course">
      <div class="actions"><label>筛选学期<select v-model="term"><option>全部学期</option><option v-for="value in terms" :key="value">{{value}}</option></select></label><button class="button" @click="startProfile(true)">{{integrated?'新增课程':'新增课程样例'}}</button></div>
      <p v-if="!loading&&!error&&!courses.length">尚未记录课程，可以新增课程档案。</p>
      <div class="course-list"><button v-for="item in visible" :key="item.id" class="panel course-card" @click="open(item.id)"><span class="term">{{item.term}}</span><h2>{{item.name}}</h2><p>{{item.teacher||'教师待记录'}} · {{item.location||'地点待记录'}}</p><span>查看课程详情 →</span></button></div>
    </template>
    <template v-else>
      <div class="actions"><button class="button button--secondary" @click="open('')">返回课程列表</button><button class="button button--secondary" @click="startProfile()">编辑档案</button></div>
      <section class="panel"><span class="term">{{course.term}}</span><h2>{{course.name}}</h2><p>{{course.teacher||'教师待记录'}} · {{course.location||'地点待记录'}}</p></section>
      <nav class="course-tabs" aria-label="课程详情分区"><button v-for="value in ['总览','课程要求','任务','资料']" :key="value" :aria-pressed="tab===value" @click="tab=value;editingRequirement='';error=''">{{value}}</button></nav>
      <section v-if="tab==='总览'" class="panel"><h2>课程总览</h2><p>已确认 {{course.requirements.filter(r=>r.state==='已确认').length}} 项要求，其余请逐项记录或核对。</p><p>{{integrated?'档案信息依据：本机用户填写，教师原文尚未核验。':'档案信息依据：合成样例／本次用户输入，未对接教师原文。'}}</p><h3>小组与分工</h3><p>{{course.group||'尚未记录小组信息'}}</p><h3>上课时间</h3><p>课程时间规则待与课表模块接入，当前不生成或修改排程占用。</p><details v-if="course.profileHistory.length" class="profile-history"><summary>档案修改历史（{{course.profileHistory.length}}）</summary><p>{{integrated?'按修改顺序保留旧值，随课程档案保存在本机。':'按修改顺序保留旧值；仅为本页样例记录，刷新后重置。'}}</p><ol><li v-for="(entry,index) in course.profileHistory" :key="index"><p>{{entry.term}} · {{entry.name}}</p><p>教师：{{entry.teacher||'未记录'}}；地点：{{entry.location||'未记录'}}</p><p>小组与分工：{{entry.group||'未记录'}}</p></li></ol></details></section>
      <section v-else-if="tab==='课程要求'" class="requirements">
        <article v-for="item in course.requirements" :key="item.id" class="panel"><div class="actions"><h2>{{item.label}}</h2><span class="state">{{item.state}}</span></div><p>{{item.value||(item.state==='明确无要求'?'已明确记录无此项要求':'尚无要求内容，不能据此视为无要求')}}</p><p class="source">依据：{{item.source||'暂无依据，待记录'}}</p>
          <form v-if="editingRequirement===item.id" class="editor" @submit.prevent="saveRequirement">
            <div class="edit-modes" role="group" aria-label="要求编辑方式"><button type="button" :aria-pressed="requirementMode==='quick'" @click="requirementMode='quick'">快捷编辑</button><button type="button" :aria-pressed="requirementMode==='full'" @click="requirementMode='full'">完整编辑</button></div>
            <p>{{requirementMode==='quick'?'适合补充一条简短要求；多条说明可切换完整编辑。':'逐行整理多条说明，对照修改前内容与依据后再保留。'}}切换方式会保留尚未应用的输入。</p>
            <label>记录状态<select v-model="requirement.state" aria-label="记录状态"><option v-for="value in requirementStates" :key="value">{{value}}</option></select></label>
            <label>要求内容<textarea v-model="requirement.value" aria-label="要求内容" aria-describedby="requirement-value-count" :class="{'full-text':requirementMode==='full'}" maxlength="2000" :placeholder="requirementMode==='full'?'可分行记录比例、条件和例外；不会自动转换为任务。':'填写要求内容'"></textarea><span id="requirement-value-count" class="source">{{requirement.value.length}} / 2000 字</span></label>
            <label>来源或用户声明<textarea v-model="requirement.source" aria-label="来源或用户声明" aria-describedby="requirement-source-count" :class="{'full-text':requirementMode==='full'}" maxlength="2000" placeholder="保留原文来源；手动填写可注明用户声明"></textarea><span id="requirement-source-count" class="source">{{requirement.source.length}} / 2000 字</span></label>
            <section v-if="requirementMode==='full'" class="change-preview" aria-label="要求修改核对"><h3>修改前</h3><p>{{item.state}}</p><p class="preserve-lines">{{item.value||'无要求内容'}}</p><p class="source preserve-lines">依据：{{item.source||'未记录'}}</p><h3>本次输入（尚未应用）</h3><p>{{requirement.state}}</p><p class="preserve-lines">{{requirement.value||'无要求内容'}}</p><p class="source preserve-lines">依据：{{requirement.source||'未记录'}}</p></section>
            <p>“明确无要求”须有依据且内容留空；空白不会自动变成无要求。取消修改会丢弃本次输入，原记录保持不变。</p><div class="actions"><button class="button" type="submit">保留修改</button><button class="button button--secondary" type="button" @click="editingRequirement='';error=''">取消修改</button></div>
          </form>
          <button v-else class="button button--secondary" @click="startRequirement(item.id)">{{commonRequirements.includes(item.label)?'编辑要求':'编辑自定义要求'}}</button>
          <details v-if="item.history.length"><summary>历史记录（{{item.history.length}}）</summary><ol><li v-for="(entry,index) in item.history" :key="index">{{entry.state}} · {{entry.value||'无内容'}}<p>依据：{{entry.source||'未记录'}}</p></li></ol></details>
        </article>
        <form class="panel editor" @submit.prevent="addCustom"><label>本课程自定义字段<input v-model="custom" maxlength="60" placeholder="例如：课堂展示"></label><button class="button button--secondary" type="submit">添加字段</button></form>
      </section>
      <section v-else class="panel"><h2>{{tab==='任务'?'课程任务':'课程资料'}}</h2><p>{{tab==='任务'?'课程任务待接入已有 Task 能力，本样例未查询任务，不能视为没有任务。':'课程资料待接入知识库授权范围，本样例未查询资料，不能视为没有资料。'}}</p></section>
    </template>
    </fieldset>
  </div>
</template>

<style scoped>
.course-content{border:0;padding:0;margin:0;min-width:0}.course-content:disabled{opacity:.7}
.requirements>article>p{white-space:pre-wrap}
.edit-modes{display:flex;flex-wrap:wrap;gap:8px}.edit-modes button{border:1px solid #a5bdb3;border-radius:8px;padding:10px 14px;background:white;color:#244a3e;font:inherit}.edit-modes button[aria-pressed=true]{background:#096b58;color:white}.editor textarea.full-text{min-height:180px}.change-preview{padding:12px;background:#f2f6f3;border-radius:10px;min-width:0}.preserve-lines{white-space:pre-wrap}
.courses-preview{max-width:780px;margin:auto;padding-bottom:40px;overflow-wrap:anywhere}.courses-preview header{margin-bottom:20px}.courses-preview h1{font-size:28px}.courses-preview h2{font-size:18px}.courses-preview h3{font-size:15px;margin-top:18px}.courses-preview p{line-height:1.7;margin:8px 0}.eyebrow,.source{font-size:12px;color:#526b68}.preview-note{padding:14px 18px;background:#e8f3ee;border-radius:16px;margin-bottom:20px}.panel{background:white;border:1px solid #dce8e2;border-radius:18px;padding:18px;min-width:0}.course-list,.requirements{display:grid;gap:12px;margin:16px 0}.course-card{text-align:left;color:inherit;cursor:pointer;font:inherit}.course-card:hover{border-color:#12816a}.course-card>span:last-child{font-size:12px;color:#08755e}.term,.state{display:inline-block;font-size:12px;color:#285e50;background:#edf4f0;padding:4px 8px;border-radius:8px}.actions{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin:12px 0}.course-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:18px 0}.course-tabs button{padding:12px 2px;border:1px solid #d5e3dc;border-radius:10px;background:white;color:#365a50}.course-tabs button[aria-pressed=true]{background:#096b58;color:white}.editor{display:grid;gap:14px}.editor label,.actions label{display:grid;gap:6px;font-size:14px}input,textarea,select{width:100%;min-width:0;box-sizing:border-box;border:1px solid #a5bdb3;border-radius:8px;padding:10px;font:inherit;color:#244a3e;background:white}textarea{min-height:80px;resize:vertical}.error{color:#a12c2c}.courses-preview button:focus-visible,.courses-preview summary:focus-visible{outline:3px solid #208c76;outline-offset:3px}details{margin-top:14px}summary{cursor:pointer}li{padding:8px 0;border-bottom:1px solid #e2ebe5}@media(min-width:650px){.course-list{grid-template-columns:1fr 1fr}}@media(max-width:390px){.panel{padding:14px}.courses-preview .button{white-space:normal}}
</style>
