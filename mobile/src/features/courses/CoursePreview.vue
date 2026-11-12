<script setup lang="ts">
import {computed,ref} from 'vue';
import {RouterLink} from 'vue-router';
import {commonRequirements,createCourse,createSamples,requirementStates,updateCourseProfile,updateRequirement,type RequirementState} from './demoModel';
withDefaults(defineProps<{integrated?:boolean}>(),{integrated:false});
const courses=ref(createSamples()),selected=ref(''),term=ref('全部学期'),tab=ref('总览'),error=ref(''),message=ref('');
const course=computed(()=>courses.value.find(item=>item.id===selected.value));
const terms=computed(()=>[...new Set(courses.value.map(item=>item.term))]);
const visible=computed(()=>courses.value.filter(item=>term.value==='全部学期'||item.term===term.value));
const creating=ref(false),editing=ref(false),editingRequirement=ref('');
const profile=ref({name:'',term:'',teacher:'',location:'',group:''});
const requirement=ref({state:'未记录' as RequirementState,value:'',source:''}),custom=ref('');
function open(id:string){selected.value=id;tab.value='总览';error.value='';message.value='';editing.value=false;editingRequirement.value='';creating.value=false}
function startProfile(isNew=false){creating.value=isNew;editing.value=true;error.value='';profile.value=isNew?{name:'',term:'',teacher:'',location:'',group:''}:{...course.value!}}
function saveProfile(){try{const data=creating.value?{...createCourse(crypto.randomUUID(),profile.value.name,profile.value.term),teacher:profile.value.teacher.trim(),location:profile.value.location.trim(),group:profile.value.group.trim()}:updateCourseProfile(course.value!,profile.value);if(creating.value)courses.value.push(data);else courses.value=courses.value.map(item=>item.id===data.id?data:item);selected.value=data.id;editing.value=false;creating.value=false;term.value='全部学期';message.value='样例已更新；刷新页面将恢复初始内容。';error.value=''}catch(e){error.value=(e as Error).message}}
function startRequirement(id:string){const item=course.value!.requirements.find(r=>r.id===id)!;requirement.value={state:item.state,value:item.value,source:item.source};editingRequirement.value=id;error.value=''}
function saveRequirement(){try{const updated=updateRequirement(course.value!,editingRequirement.value,requirement.value);courses.value=courses.value.map(item=>item.id===updated.id?updated:item);editingRequirement.value='';error.value='';message.value='本次人工修改和原记录已分别保留在样例历史中。'}catch(e){error.value=(e as Error).message}}
function addCustom(){const label=custom.value.trim();if(!label){error.value='请填写自定义字段名称。';return}if(course.value!.requirements.some(item=>item.label===label)){error.value='本课程已有同名要求。';return}course.value!.requirements.push({id:crypto.randomUUID(),label,state:'未记录',value:'',source:'',history:[]});custom.value='';error.value=''}
</script>

<template>
  <div class="page courses-preview">
    <RouterLink v-if="integrated" class="text-link" to="/home">← 返回工作台</RouterLink>
    <header><p class="eyebrow">有绪 CampusWeave · 繁事有绪，办事有方。</p><h1>我的课程</h1><p>按学期整理课程，让每条要求都有依据。</p></header>
    <aside class="preview-note"><strong>课程交互样例</strong><p>全部为合成数据，修改仅在本页内存中生效，刷新后重置。不会读取或保存账户、课表、任务和资料。</p></aside>
    <p v-if="message" role="status">{{message}}</p><p v-if="error" role="alert" class="error">{{error}}</p>
    <form v-if="editing" class="panel editor" @submit.prevent="saveProfile">
      <h2>{{creating?'新增课程样例':'编辑课程档案'}}</h2>
      <label>课程名称<input v-model="profile.name" maxlength="100" required></label><label>学期<input v-model="profile.term" placeholder="例如：2026 秋季" maxlength="60" required></label>
      <label>教师<input v-model="profile.teacher" maxlength="100"></label><label>上课地点<input v-model="profile.location" maxlength="200"></label>
      <label>小组成员与分工<textarea v-model="profile.group" maxlength="1000" placeholder="记录成员与分工；关联作业待接入"></textarea></label>
      <div class="actions"><button class="button" type="submit">应用到样例</button><button class="button button--secondary" type="button" @click="editing=false;creating=false;error=''">取消编辑</button></div>
    </form>
    <template v-else-if="!course">
      <div class="actions"><label>筛选学期<select v-model="term"><option>全部学期</option><option v-for="value in terms" :key="value">{{value}}</option></select></label><button class="button" @click="startProfile(true)">新增课程样例</button></div>
      <div class="course-list"><button v-for="item in visible" :key="item.id" class="panel course-card" @click="open(item.id)"><span class="term">{{item.term}}</span><h2>{{item.name}}</h2><p>{{item.teacher||'教师待记录'}} · {{item.location||'地点待记录'}}</p><span>查看课程详情 →</span></button></div>
    </template>
    <template v-else>
      <div class="actions"><button class="button button--secondary" @click="open('')">返回课程列表</button><button class="button button--secondary" @click="startProfile()">编辑档案</button></div>
      <section class="panel"><span class="term">{{course.term}}</span><h2>{{course.name}}</h2><p>{{course.teacher||'教师待记录'}} · {{course.location||'地点待记录'}}</p></section>
      <nav class="course-tabs" aria-label="课程详情分区"><button v-for="value in ['总览','课程要求','任务','资料']" :key="value" :aria-pressed="tab===value" @click="tab=value;editingRequirement='';error=''">{{value}}</button></nav>
      <section v-if="tab==='总览'" class="panel"><h2>课程总览</h2><p>已确认 {{course.requirements.filter(r=>r.state==='已确认').length}} 项要求，其余请逐项记录或核对。</p><p>档案信息依据：合成样例／本次用户输入，未对接教师原文。</p><h3>小组与分工</h3><p>{{course.group||'尚未记录小组信息'}}</p><h3>上课时间</h3><p>课程时间规则待与课表模块接入，当前不生成或修改排程占用。</p><details v-if="course.profileHistory.length" class="profile-history"><summary>档案修改历史（{{course.profileHistory.length}}）</summary><p>按修改顺序保留旧值；仅为本页样例记录，刷新后重置。</p><ol><li v-for="(entry,index) in course.profileHistory" :key="index"><p>{{entry.term}} · {{entry.name}}</p><p>教师：{{entry.teacher||'未记录'}}；地点：{{entry.location||'未记录'}}</p><p>小组与分工：{{entry.group||'未记录'}}</p></li></ol></details></section>
      <section v-else-if="tab==='课程要求'" class="requirements">
        <article v-for="item in course.requirements" :key="item.id" class="panel"><div class="actions"><h2>{{item.label}}</h2><span class="state">{{item.state}}</span></div><p>{{item.value||(item.state==='明确无要求'?'已明确记录无此项要求':'尚无要求内容，不能据此视为无要求')}}</p><p class="source">依据：{{item.source||'暂无依据，待记录'}}</p>
          <form v-if="editingRequirement===item.id" class="editor" @submit.prevent="saveRequirement"><label>记录状态<select v-model="requirement.state"><option v-for="value in requirementStates" :key="value">{{value}}</option></select></label><label>要求内容<textarea v-model="requirement.value" maxlength="2000"></textarea></label><label>来源或用户声明<textarea v-model="requirement.source" maxlength="2000" placeholder="保留原文来源；手动填写可注明用户声明"></textarea></label><p>“明确无要求”须有依据且内容留空；空白不会自动变成无要求。</p><div class="actions"><button class="button" type="submit">保留修改</button><button class="button button--secondary" type="button" @click="editingRequirement='';error=''">取消修改</button></div></form>
          <button v-else class="button button--secondary" @click="startRequirement(item.id)">{{commonRequirements.includes(item.label)?'编辑要求':'编辑自定义要求'}}</button>
          <details v-if="item.history.length"><summary>历史记录（{{item.history.length}}）</summary><ol><li v-for="(entry,index) in item.history" :key="index">{{entry.state}} · {{entry.value||'无内容'}}<p>依据：{{entry.source||'未记录'}}</p></li></ol></details>
        </article>
        <form class="panel editor" @submit.prevent="addCustom"><label>本课程自定义字段<input v-model="custom" maxlength="60" placeholder="例如：课堂展示"></label><button class="button button--secondary" type="submit">添加字段</button></form>
      </section>
      <section v-else class="panel"><h2>{{tab==='任务'?'课程任务':'课程资料'}}</h2><p>{{tab==='任务'?'课程任务待接入已有 Task 能力，本样例未查询任务，不能视为没有任务。':'课程资料待接入知识库授权范围，本样例未查询资料，不能视为没有资料。'}}</p></section>
    </template>
  </div>
</template>

<style scoped>
.courses-preview{max-width:780px;margin:auto;padding-bottom:40px;overflow-wrap:anywhere}.courses-preview header{margin-bottom:20px}.courses-preview h1{font-size:28px}.courses-preview h2{font-size:18px}.courses-preview h3{font-size:15px;margin-top:18px}.courses-preview p{line-height:1.7;margin:8px 0}.eyebrow,.source{font-size:12px;color:#526b68}.preview-note{padding:14px 18px;background:#e8f3ee;border-radius:16px;margin-bottom:20px}.panel{background:white;border:1px solid #dce8e2;border-radius:18px;padding:18px;min-width:0}.course-list,.requirements{display:grid;gap:12px;margin:16px 0}.course-card{text-align:left;color:inherit;cursor:pointer;font:inherit}.course-card:hover{border-color:#12816a}.course-card>span:last-child{font-size:12px;color:#08755e}.term,.state{display:inline-block;font-size:12px;color:#285e50;background:#edf4f0;padding:4px 8px;border-radius:8px}.actions{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin:12px 0}.course-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:18px 0}.course-tabs button{padding:12px 2px;border:1px solid #d5e3dc;border-radius:10px;background:white;color:#365a50}.course-tabs button[aria-pressed=true]{background:#096b58;color:white}.editor{display:grid;gap:14px}.editor label,.actions label{display:grid;gap:6px;font-size:14px}input,textarea,select{width:100%;min-width:0;box-sizing:border-box;border:1px solid #a5bdb3;border-radius:8px;padding:10px;font:inherit;color:#244a3e;background:white}textarea{min-height:80px;resize:vertical}.error{color:#a12c2c}.courses-preview button:focus-visible,.courses-preview summary:focus-visible{outline:3px solid #208c76;outline-offset:3px}details{margin-top:14px}summary{cursor:pointer}li{padding:8px 0;border-bottom:1px solid #e2ebe5}@media(min-width:650px){.course-list{grid-template-columns:1fr 1fr}}@media(max-width:390px){.panel{padding:14px}.courses-preview .button{white-space:normal}}
</style>
