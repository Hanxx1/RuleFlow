<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import {RouterLink,useRoute,useRouter} from 'vue-router';
import {Capacitor} from '@capacitor/core';
import {api,apiBase,auth,checkApiHealth} from '../core/http';
import {useAccountStore} from '../stores/account';
import {useCasesStore} from '../features/cases/store';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import StatusBadge from '../components/StatusBadge.vue';
import TaskTimeline from '../components/TaskTimeline.vue';
import {guideFaqs} from '../content/guide';
const helpFaqs=guideFaqs.filter(faq=>['partial','unknown','offline','ai'].includes(faq.id));

const route=useRoute(),router=useRouter(),account=useAccountStore(),cases=useCasesStore();
const email=ref(''),password=ref(''),token=ref(''),caseTitle=ref(''),category=ref('other');
const busy=ref(false),message=ref(''),error=ref('');
const profile=ref<any>({student_type:'undergraduate',enrollment_year:2024,college:'',major:'',rank_percent:null,team_size:null,graduation_year:null});
const title=computed(()=>String(route.meta.title||'知事 RuleFlow'));
const caseId=computed(()=>String(route.params.id||''));
const caseTabs=computed(()=>caseId.value?[['概览',`/cases/${caseId.value}`],['规则',`/cases/${caseId.value}/rules`],['材料',`/cases/${caseId.value}/materials`],['流程',`/cases/${caseId.value}/flow`],['来源',`/cases/${caseId.value}/sources`]]:[]);
const authDescription=computed(()=>route.path==='/auth/login'?'登录后查看你的真实事项与计划':route.path==='/auth/register'?'创建账户，数据将按用户隔离保存':route.path==='/auth/verify'?'输入一次性令牌完成邮箱验证':'安全重置账户密码');
function fail(e:any){error.value=e?.message||'操作失败，请重试'}
function analysisModeLabel(mode:string){return mode==='llm'?'AI 辅助分析':mode==='local_fallback'?'AI 调用失败，已回退本地规则':'本地规则分析（未调用 AI）'}
async function load(){
  error.value='';message.value='';
  try{
    if(route.path==='/profile')profile.value=account.signedIn?{...profile.value,...await api('/api/v1/profile')}:{...profile.value,...JSON.parse(localStorage.getItem('zhishi-profile')||'{}')};
    if(caseId.value&&route.path.startsWith('/cases/')){await cases.loadOne(caseId.value);await cases.loadResources(caseId.value);if(route.path.endsWith('/flow'))await cases.loadPlan(caseId.value)}
    if(route.path==='/settings/devices'&&account.signedIn)await account.loadDevices();
  }catch(e){fail(e)}
}
watch(()=>route.fullPath,load,{immediate:true});
async function submitAuth(){busy.value=true;error.value='';message.value='';try{if(route.path==='/auth/login'){await account.login(email.value,password.value);await router.replace('/home')}else if(route.path==='/auth/register'){const d=await auth.register(email.value,password.value);token.value=d.development_verification_token||'';message.value='注册成功，请完成邮箱验证。开发模式已填入验证令牌。'}else if(route.path==='/auth/verify'){await auth.verify(token.value);message.value='邮箱已验证，现在可以登录。'}else if(route.path==='/auth/reset'){if(!token.value){const d=await auth.resetRequest(email.value);token.value=d.development_reset_token||'';message.value=d.message}else{await auth.reset(token.value,password.value);message.value='密码已重置。'}}}catch(e){fail(e)}finally{busy.value=false}}
async function createCase(){busy.value=true;error.value='';try{const x=await cases.create(caseTitle.value,category.value);await router.push('/cases/'+x.id)}catch(e){fail(e)}finally{busy.value=false}}
async function setTask(id:string,status:string){try{await cases.setTask(id,status)}catch(e){fail(e)}}
async function saveProfile(){busy.value=true;error.value='';try{const clean=Object.fromEntries(Object.entries(profile.value).filter(([,v])=>v!==''&&v!==null));if(account.signedIn)await api('/api/v1/profile',{method:'PUT',body:JSON.stringify({facts:clean})});else localStorage.setItem('zhishi-profile',JSON.stringify(clean));message.value=account.signedIn?'画像已保存并用于账户事项判断。':'本机画像已保存；当前演示事项仍使用固定演示画像。'}catch(e){fail(e)}finally{busy.value=false}}
async function copyDiagnostics(){error.value='';message.value='';const details=['知事 RuleFlow 1.0.0',`运行平台：${Capacitor.getPlatform()}`,`当前页面：${route.path}`,`服务地址：${apiBase}`,`账户状态：${account.signedIn?'已登录':'未登录'}`,`生成时间：${new Date().toISOString()}`].join('\n');try{await navigator.clipboard.writeText(details);message.value='诊断信息已复制，可连同问题描述发送给支持人员。'}catch{error.value='无法复制诊断信息，请检查浏览器剪贴板权限。'}}
async function checkConnection(){busy.value=true;error.value='';message.value='';try{const result=await checkApiHealth();if((result.data||result).status!=='ok')throw Error('服务响应未就绪');message.value='应用已成功连接后端。'}catch(e){fail(e)}finally{busy.value=false}}
</script>

<template>
  <div v-if="route.path==='/welcome'" class="welcome-page">
    <div class="welcome-page__brand"><span>知</span><b>知事</b></div><div class="welcome-page__visual"><img src="/assets/illustrations/hero_notice_checklist.png" alt=""></div><div class="welcome-page__copy">
      <h1>把复杂通知，变成清晰行动。</h1><p>从原文证据到规则、材料要求与执行步骤；信息不足时，知事会如实告诉你。</p></div><div class="welcome-page__actions"><RouterLink class="button button--primary button--block" to="/auth/login">登录账户</RouterLink><RouterLink class="button button--secondary button--block" to="/home">先体验离线样例</RouterLink></div><small>账户数据、本机数据与演示数据相互隔离</small>
  </div>

  <div v-else :class="['page','page--utility',{'page--auth':route.path.startsWith('/auth/')}]">
    <AppHeader :title="title" :subtitle="route.path.startsWith('/auth/')?authDescription:undefined">
      <template #action><RouterLink v-if="route.path.startsWith('/auth/')" class="icon-button icon-button--plain" to="/welcome" aria-label="返回欢迎页">←</RouterLink><button v-else class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></template>
    </AppHeader>
    <div v-if="error" class="notice notice--danger" role="alert">{{error}}</div><div v-if="message" class="notice notice--success">{{message}}</div>

    <form v-if="route.path.startsWith('/auth/')" class="surface-card form-card" @submit.prevent="submitAuth">
      <label v-if="route.path!=='/auth/verify'">邮箱<input v-model="email" type="email" autocomplete="email" placeholder="name@example.com" required></label>
      <label v-if="route.path==='/auth/login'||route.path==='/auth/register'||(route.path==='/auth/reset'&&token)">密码<input v-model="password" type="password" minlength="12" autocomplete="current-password" placeholder="至少 12 位" required></label>
      <label v-if="route.path==='/auth/verify'||(route.path==='/auth/reset'&&token)">验证令牌<input v-model="token" autocomplete="one-time-code" placeholder="输入一次性令牌" required></label>
      <button class="button button--primary button--block" :disabled="busy">{{busy?'处理中…':route.path==='/auth/reset'&&!token?'发送重置邮件':'提交'}}</button>
      <p class="capability-note" style="overflow-wrap:anywhere">服务地址：{{apiBase}}</p><button class="button button--secondary button--block" type="button" :disabled="busy" @click="checkConnection">检查服务连接</button><div class="auth-links"><RouterLink to="/auth/login">登录</RouterLink><RouterLink to="/auth/register">注册</RouterLink><RouterLink to="/auth/verify">验证邮箱</RouterLink><RouterLink to="/auth/reset">忘记密码</RouterLink></div>
    </form>

    <form v-else-if="route.path==='/cases/new'" class="surface-card form-card" @submit.prevent="createCase"><label>事项名称<input v-model="caseTitle" required maxlength="300" placeholder="这是一件什么事？"></label><label>分类<select v-model="category"><option value="academic">教务</option><option value="award">奖助评优</option><option value="exam">考试</option><option value="competition">竞赛</option><option value="career">就业实习</option><option value="research">科研申报</option><option value="other">其他</option></select></label><button class="button button--primary button--block" :disabled="busy||!account.signedIn">{{account.signedIn?'创建事项':'登录后可创建真实事项'}}</button></form>

    <template v-else-if="route.path.startsWith('/cases/')">
      <nav class="detail-tabs"><RouterLink v-for="tab in caseTabs" :key="tab[1]" :to="tab[1]">{{tab[0]}}</RouterLink></nav>
      <AppState v-if="cases.loading" kind="loading" title="正在读取事项"/>
      <template v-else-if="cases.selected">
        <section class="case-detail-hero"><div class="case-detail-hero__top"><StatusBadge :value="cases.selected.relevance"/></div><h2>{{cases.selected.title}}</h2><p>{{cases.selected.deadline?'截止 '+cases.selected.deadline:'截止时间待核对'}} · {{cases.selected.status}}</p></section>
        <section v-if="cases.resources?.analysis" class="analysis-panel"><div class="analysis-panel__top"><div><span class="text-label">分析方式</span><h3>{{analysisModeLabel(cases.resources.analysis.mode)}}</h3></div><span class="ai-chip">{{cases.resources.analysis.mode==='llm'?'AI':'规则'}}</span></div><p v-if="cases.resources.analysis.summary">{{cases.resources.analysis.summary}}</p><div v-if="cases.resources.analysis.questions?.length" class="analysis-notes"><b>还需要核对</b><ul><li v-for="item in cases.resources.analysis.questions" :key="item">{{item}}</li></ul></div><div v-if="cases.resources.analysis.review_reasons?.length" class="analysis-notes"><b>复核提示</b><ul><li v-for="item in cases.resources.analysis.review_reasons" :key="item">{{item}}</li></ul></div></section>
        <div v-if="route.path===`/cases/${caseId}`" class="detail-grid"><section class="surface-card"><span class="text-label">当前判断</span><h3>{{cases.selected.relevance}}</h3><p>UNKNOWN 表示证据或个人资料不足，不等于“不符合”。</p></section><section class="surface-card"><span class="text-label">下一步</span><h3>核对并执行</h3><p>查看规则、材料要求与流程；所有结论均可回到原文。</p></section></div>
        <TaskTimeline v-else-if="route.path.endsWith('/flow')&&cases.plan?.ordered_tasks?.length" :tasks="cases.plan.ordered_tasks" @change="setTask"/>
        <AppState v-else-if="route.path.endsWith('/flow')" title="尚未生成有证据支撑的任务"/>
        <div v-else-if="route.path.endsWith('/sources')" class="resource-list"><AppState v-if="!cases.resources?.evidence?.length" title="尚无来源证据"/><article v-for="item in cases.resources?.evidence||[]" :key="item.id" class="surface-card evidence-card"><span class="text-label">{{item.source_name}} · {{item.locator}}</span><p>{{item.text}}</p><small>EvidenceRef · {{item.id}}</small></article></div>
        <div v-else-if="route.path.endsWith('/rules')" class="resource-list"><AppState v-if="!cases.resources?.rules?.length" title="尚无已确认规则" description="UNKNOWN 不会被当作不符合。"/><article v-for="item in cases.resources?.rules||[]" :key="item.id" class="surface-card"><span class="text-label">规则</span><h3>{{item.label}}</h3><p>证据：{{item.evidence_ids.join('、')}}</p></article></div>
        <div v-else-if="route.path.endsWith('/materials')" class="resource-list"><AppState v-if="!cases.resources?.materials?.length&&!cases.resources?.files?.length" title="还没有材料要求或关联文件"/><article v-for="item in cases.resources?.materials||[]" :key="item.id" class="surface-card"><span class="text-label">材料要求</span><h3>{{item.title}}</h3><p>{{item.state}} · EvidenceRef {{item.evidence_ids.join('、')}}</p></article><article v-for="item in cases.resources?.files||[]" :key="item.id" class="surface-card"><span class="text-label">已关联文件</span><h3>{{item.name}}</h3><p>{{item.category}} · {{item.size}} bytes</p><RouterLink class="text-link" :to="{path:'/vault',query:{case:caseId}}">在材料库中查看</RouterLink></article><RouterLink class="button button--secondary button--block" :to="{path:'/vault',query:{case:caseId}}">管理关联材料</RouterLink></div>
        <AppState v-else title="当前事项没有待处理内容" description="没有检测到需要在此页面补充或复核的信息。"/>
      </template>
    </template>

    <form v-else-if="route.path==='/profile'" class="surface-card form-card" @submit.prevent="saveProfile"><label>身份<select v-model="profile.student_type"><option value="undergraduate">本科生</option><option value="graduate">研究生</option><option value="teacher">教师</option><option value="other">其他</option></select></label><div class="form-grid"><label>入学年份<input v-model.number="profile.enrollment_year" type="number" min="1990" max="2100"></label><label>毕业年份<input v-model.number="profile.graduation_year" type="number" min="1990" max="2100" placeholder="可留空"></label></div><label>学院<input v-model="profile.college" placeholder="可留空"></label><label>专业<input v-model="profile.major" placeholder="可留空"></label><div class="form-grid"><label>排名百分比<input v-model.number="profile.rank_percent" type="number" min="0" max="100" placeholder="未知可留空"></label><label>团队人数<input v-model.number="profile.team_size" type="number" min="1" placeholder="未知可留空"></label></div><button class="button button--primary button--block" :disabled="busy">保存画像</button><p class="capability-note">未填写字段保持 UNKNOWN，系统不会因此判断为不符合。</p></form>

    <template v-else-if="route.path==='/settings/devices'"><AppState v-if="!account.signedIn" title="登录后查看设备" description="当前没有可展示的账户会话。"><RouterLink class="button button--primary" to="/auth/login">去登录</RouterLink></AppState><div v-else class="resource-list"><article v-for="item in account.devices" :key="item.id" class="surface-card device-card"><span class="device-card__icon"><img src="/assets/icons/features/icon_登录设备.svg" alt=""></span><div><h3>{{item.device_name||'未知设备'}}</h3><p>最近记录 {{item.last_used_at}}</p></div><StatusBadge value="active"/></article><AppState v-if="!account.devices.length" title="没有有效设备会话"/></div></template>

    <template v-else-if="route.path==='/help'">
      <section class="surface-card prose-card"><h2>完整使用指南</h2><p>从导入来源、核对日期与步骤，到个人资料、课表排程、材料和隐私分享，按场景查找操作说明。</p><RouterLink class="button button--primary button--block" style="margin-top:14px" to="/guide?from=/help">打开使用指南</RouterLink></section>
      <section class="surface-card prose-card" style="margin-top:16px"><h2>常见问题</h2><article v-for="faq in helpFaqs" :key="faq.id"><h3>{{faq.question}}</h3><p>{{faq.answer}}</p><RouterLink class="text-link" :to="{path:'/guide',query:{topic:faq.topic,from:'/help'}}">查看对应操作 →</RouterLink></article></section>
      <section class="surface-card prose-card" style="margin-top:16px"><h2>反馈与诊断</h2><p>记录问题页面、复现步骤和实际结果。可复制不含原文、令牌和个人资料的运行信息，并自行提供给项目支持人员。</p><button class="button button--secondary button--block" type="button" style="margin-top:14px" @click="copyDiagnostics">复制诊断信息</button></section>
    </template>
    <template v-else-if="route.path==='/about'"><section class="about-card"><div class="about-card__mark">知</div><h2>知事 RuleFlow</h2><p>把复杂通知变成可追溯的规则、材料要求与执行步骤。</p><dl><div><dt>移动端版本</dt><dd>1.0.0</dd></div><div><dt>数据原则</dt><dd>演示、本机与账户空间隔离</dd></div><div><dt>判断原则</dt><dd>证据不足时保持 UNKNOWN</dd></div></dl></section></template>
    <template v-else-if="route.path==='/settings/privacy'"><section class="surface-card prose-card"><h2>导入确认</h2><p>导入前保留本地隐私预览与明确确认；文件访问和上传仍需授权。</p></section><section class="surface-card prose-card"><h2>当前账户数据范围</h2><p>{{account.signedIn?'事项、画像、材料、日程和导入批次只保存在当前登录账户空间，并与其他 owner 隔离。':'当前未登录；仅可查看明确标记的本机演示内容，新的账户数据不会写入演示空间。'}}</p></section></template>
    <template v-else><AppState title="暂无可展示内容" description="请返回工作台继续使用导入、事项、计划和材料等已连接功能。"/></template>
  </div>
</template>
