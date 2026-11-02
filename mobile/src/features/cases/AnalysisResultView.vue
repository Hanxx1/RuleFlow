<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import AppHeader from '../../components/AppHeader.vue';
import GuideLink from '../../components/GuideLink.vue';
import AppState from '../../components/AppState.vue';
import CaseContextHeader from '../../components/CaseContextHeader.vue';
import LocalMatchPanel from '../../components/LocalMatchPanel.vue';
import AnalysisSection from '../../components/AnalysisSection.vue';
import EvidenceLink from '../../components/EvidenceLink.vue';
import EvidenceBottomSheet from '../../components/EvidenceBottomSheet.vue';
import MaterialRequirementList from '../../components/MaterialRequirementList.vue';
import AnalysisReviewPanel from '../../components/AnalysisReviewPanel.vue';
import AnalysisHistoryPanel from '../../components/AnalysisHistoryPanel.vue';
import AttachmentPanel from '../../components/AttachmentPanel.vue';
import {useCasesStore} from './store';
import {useAccountStore} from '../../stores/account';
import analysisHero from '../../assets/illustrations/hero_structured_analysis.webp';

const route=useRoute(),router=useRouter(),cases=useCasesStore(),account=useAccountStore();
const pageError=ref(''),pageMessage=ref(''),evidenceOpen=ref(false),activeEvidence=ref<any|null>(null),editing=ref(false),saving=ref(false);
const draft=ref<any>({title:'',category:'other',status:'draft',deadline:''});
const caseId=computed(()=>String(route.params.id));
const resources=computed(()=>cases.resources||{});
async function load(){pageError.value='';try{await cases.loadOne(caseId.value);await cases.loadResources(caseId.value)}catch(e:any){pageError.value=e?.message||'事项解析结果读取失败'}}
onMounted(load);watch(caseId,load);
function evidenceById(id?:string){return resources.value.evidence?.find((item:any)=>item.id===id)||null}
function openEvidence(item:any){const id=item?.evidence_ids?.[0]||item?.id;activeEvidence.value=evidenceById(id)||item;evidenceOpen.value=true}
function beginEdit(){const item=cases.selected;draft.value={title:item.title,category:item.category,status:item.status,deadline:item.deadline?.slice(0,10)||''};editing.value=true;pageMessage.value=''}
async function saveCase(){saving.value=true;pageError.value='';try{await cases.updateCase(caseId.value,{...draft.value,deadline:draft.value.deadline||null});editing.value=false;pageMessage.value='事项信息已保存。'}catch(e:any){pageError.value=e?.message||'事项保存失败'}finally{saving.value=false}}
const deadlineEvidence=computed(()=>cases.selected?.deadline_evidence_ids?.map((id:string)=>evidenceById(id)).filter(Boolean)||[]);
const deadlineSourceLabel=computed(()=>({document:'来自导入文档',knowledge:'来自规则知识',user_input:'由你填写',generated:'系统生成，待核对'} as Record<string,string>)[cases.selected?.deadline_source]||'来源待核对');
</script>

<template>
  <div class="page page--product">
    <AppHeader title="解析结果"><template #action><div class="header-actions"><button v-if="account.signedIn&&cases.selected" class="button button--small button--secondary" type="button" @click="beginEdit">编辑</button><button class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></div></template></AppHeader>
    <GuideLink topic="analysis" label="如何核对结果、日期和行动步骤？"/>
    <div v-if="pageError" class="notice notice--danger">{{pageError}}</div><div v-if="pageMessage" class="notice notice--success">{{pageMessage}}</div>
    <AppState v-if="cases.loading&&!cases.selected" kind="loading" title="正在读取解析结果"/>
    <template v-else-if="cases.selected">
      <section class="product-hero product-hero--analysis"><div><h2>原文已经整理成行动信息。</h2><p>只展示当前接口实际返回的时间、材料、规则与步骤。</p></div><img :src="analysisHero" alt="" decoding="async"></section>
      <CaseContextHeader :item="cases.selected"/>
      <AttachmentPanel :case-id="caseId" :inventory="resources.attachments" @changed="load"/>
      <p v-if="cases.selected.source_url" class="notice">公开通知演示 · <a :href="cases.selected.source_url" target="_blank" rel="noopener noreferrer">查看学校官网原文</a> · 日期与资格仍需核对</p>
      <form v-if="editing" class="surface-card form-card case-edit-form" @submit.prevent="saveCase"><label>事项标题<input v-model="draft.title" required maxlength="300"></label><div class="form-grid"><label>分类<select v-model="draft.category"><option value="academic">教务</option><option value="award">奖助评优</option><option value="exam">考试</option><option value="competition">竞赛</option><option value="career">就业实习</option><option value="research">科研申报</option><option value="other">其他</option></select></label><label>状态<select v-model="draft.status"><option value="draft">草稿</option><option value="review">待复核</option><option value="in_progress">进行中</option><option value="completed">已完成</option><option value="archived">已归档</option></select></label></div><label>截止日期<input v-model="draft.deadline" type="date"></label><div class="button-row"><button class="button button--secondary" type="button" @click="editing=false">取消</button><button class="button button--primary" :disabled="saving">{{saving?'保存中…':'保存事项'}}</button></div></form>
      <section v-if="resources.analysis" class="analysis-summary"><div><span class="text-label">分析说明</span><h3>{{resources.analysis.summary||'解析已完成，等待人工核对。'}}</h3></div><ul v-if="resources.analysis.questions?.length"><li v-for="item in resources.analysis.questions" :key="item">{{item}}</li></ul><p v-if="resources.analysis.review_reasons?.length">复核提示：{{resources.analysis.review_reasons.join('；')}}</p></section>
      <LocalMatchPanel :resources="cases.resources" :case-id="caseId" @evaluated="value=>cases.selected.relevance=value"/>
      <AnalysisReviewPanel v-if="account.signedIn&&!caseId.startsWith('demo-')" :case-id="caseId" :revision-key="cases.selected.updated_at" @confirmed="load"/>
      <AnalysisHistoryPanel v-if="account.signedIn&&!caseId.startsWith('demo-')" :case-id="caseId" @changed="load"/>
      <AnalysisSection title="关键时间">
        <div v-if="cases.selected.deadline" class="key-time-card"><span>截止时间</span><strong>{{cases.selected.deadline}}</strong><small>{{deadlineSourceLabel}}</small><EvidenceLink v-if="deadlineEvidence.length" @open="openEvidence(deadlineEvidence[0])"/></div>
        <p v-else class="missing-copy">未识别到明确截止时间。</p>
      </AnalysisSection>
      <AnalysisSection title="材料要求" :count="resources.materials?.length||0">
        <MaterialRequirementList v-if="resources.materials?.length" :items="resources.materials" @evidence="openEvidence"/>
        <p v-else class="missing-copy">未识别到有原文证据支撑的材料要求。</p>
      </AnalysisSection>
      <AnalysisSection title="已关联文件" :count="resources.files?.length||0"><div v-if="resources.files?.length" class="linked-file-list"><RouterLink v-for="file in resources.files" :key="file.id" :to="{path:'/vault',query:{case:caseId}}"><b>{{file.name}}</b><small>{{file.category}} · {{file.size}} bytes</small><span>›</span></RouterLink></div><p v-else class="missing-copy">还没有从材料库关联文件。</p><RouterLink class="inline-route-link" :to="{path:'/vault',query:{case:caseId}}">打开材料库 <span>›</span></RouterLink></AnalysisSection>
      <AnalysisSection title="执行步骤" :count="resources.tasks?.length||0">
        <div v-if="resources.tasks?.length" class="compact-task-list"><article v-for="(task,index) in resources.tasks" :key="task.id"><span>{{index+1}}</span><div><strong>{{task.title}}</strong><small v-if="task.deadline">{{task.deadline}}</small></div><EvidenceLink v-if="task.evidence_ids?.length" @open="openEvidence(task)"/></article></div>
        <p v-else class="missing-copy">尚未生成有证据支撑的执行步骤。</p>
        <RouterLink class="inline-route-link" :to="`/cases/${caseId}/flow`">打开完整执行流程 <span>›</span></RouterLink>
      </AnalysisSection>
      <AnalysisSection title="规则" :count="resources.rules?.length||0">
        <div v-if="resources.rules?.length" class="rule-summary-list"><article v-for="rule in resources.rules" :key="rule.id"><div><strong>{{rule.label}}</strong><small>结论以现有画像与规则计算为准</small></div><EvidenceLink v-if="rule.evidence_ids?.length" @open="openEvidence(rule)"/></article></div>
        <p v-else class="missing-copy">尚无已确认的规则；未知不会被当作不符合。</p>
      </AnalysisSection>
      <AnalysisSection title="继续核对"><nav class="capability-links"><RouterLink :to="`/cases/${caseId}/relevance`"><b>相关性判断</b><small>查看资料与条件</small><span>›</span></RouterLink><RouterLink :to="`/cases/${caseId}/knowledge`"><b>规则依据</b><small>查看通知证据与匹配条款</small><span>›</span></RouterLink><RouterLink :to="{path:'/plan',query:{tab:'schedule',case:caseId}}"><b>安排时间</b><small>进入执行计划的日程安排</small><span>›</span></RouterLink><RouterLink :to="`/cases/${caseId}/sources`"><b>全部来源</b><small>{{resources.evidence?.length||0}} 条 EvidenceRef</small><span>›</span></RouterLink></nav></AnalysisSection>
    </template>
    <EvidenceBottomSheet :open="evidenceOpen" :evidence="activeEvidence" @close="evidenceOpen=false"/>
  </div>
</template>
