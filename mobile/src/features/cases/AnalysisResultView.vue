<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import AppHeader from '../../components/AppHeader.vue';
import GuideLink from '../../components/GuideLink.vue';
import AppState from '../../components/AppState.vue';
import StatusBadge from '../../components/StatusBadge.vue';
import LocalMatchPanel from '../../components/LocalMatchPanel.vue';
import AnalysisSection from '../../components/AnalysisSection.vue';
import EvidenceLink from '../../components/EvidenceLink.vue';
import EvidenceBottomSheet from '../../components/EvidenceBottomSheet.vue';
import MaterialRequirementList from '../../components/MaterialRequirementList.vue';
import AnalysisReviewPanel from '../../components/AnalysisReviewPanel.vue';
import AnalysisHistoryPanel from '../../components/AnalysisHistoryPanel.vue';
import AttachmentPanel from '../../components/AttachmentPanel.vue';
import {useCasesStore} from './store';
import {useCaseEditor} from './useCaseEditor';
import {useAccountStore} from '../../stores/account';


const route=useRoute(),router=useRouter(),cases=useCasesStore(),account=useAccountStore();
const pageError=ref(''),evidenceOpen=ref(false),activeEvidence=ref<any|null>(null);
const caseId=computed(()=>String(route.params.id));
const {editing,saving,pageMessage,draft,beginEdit,saveCase}=useCaseEditor(caseId,pageError);
const resources=computed(()=>cases.resources||{});
async function load(){pageError.value='';try{await cases.loadOne(caseId.value);await cases.loadResources(caseId.value)}catch(e:any){pageError.value=e?.message||'事项解析结果读取失败'}}
onMounted(load);watch(caseId,()=>{evidenceOpen.value=false;activeEvidence.value=null;load()});
function evidenceById(id?:string){return resources.value.evidence?.find((item:any)=>item.id===id)||null}
function openEvidence(item:any){const id=item?.evidence_ids?.[0]||item?.id;activeEvidence.value=evidenceById(id)||item;evidenceOpen.value=true}
const deadlineEvidence=computed(()=>cases.selected?.deadline_evidence_ids?.map((id:string)=>evidenceById(id)).filter(Boolean)||[]);
const deadlineSourceLabel=computed(()=>({document:'来自导入文档',knowledge:'来自规则知识',user_input:'由你填写',generated:'系统生成，待核对'} as Record<string,string>)[cases.selected?.deadline_source]||'来源待核对');
</script>

<template>
  <div class="page page--product analysis-result">
    <AppHeader title="解析结果"><template #action><div class="header-actions"><button v-if="account.signedIn&&cases.selected" class="button button--small button--secondary" type="button" @click="beginEdit">编辑</button><button class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></div></template></AppHeader>

    <div v-if="pageError" class="notice notice--danger">{{pageError}}</div><div v-if="pageMessage" class="notice notice--success">{{pageMessage}}</div>
    <AppState v-if="cases.loading&&!cases.selected" kind="loading" title="正在读取解析结果"/>
    <template v-else-if="cases.selected">
      <section class="surface-card notice-overview" aria-label="核对通知">
        <div class="notice-overview__label"><span class="text-label">核对通知</span><StatusBadge :value="cases.selected.status"/></div>
        <h2>{{cases.selected.title}}</h2>
        <div v-if="cases.selected.deadline" class="notice-deadline"><span>截止时间</span><strong>{{cases.selected.deadline}}</strong><small>{{deadlineSourceLabel}}</small><EvidenceLink v-if="deadlineEvidence.length" @open="openEvidence(deadlineEvidence[0])"/></div>
        <p v-else class="notice-overview__hint">截止日期尚未确认，请核对下方日期与行动。</p>
        <RouterLink :to="`/cases/${caseId}/sources`" class="text-button">查看通知原文 · {{resources.evidence?.length||0}} 条依据</RouterLink>
        <a v-if="account.signedIn&&!caseId.startsWith('demo-')" class="inline-route-link" href="#analysis-review">核对日期与行动 <span>↓</span></a>
      </section>
      <p v-if="cases.selected.source_url" class="notice">公开通知演示 · <a :href="cases.selected.source_url" target="_blank" rel="noopener noreferrer">查看学校官网原文</a> · 日期与资格仍需核对</p>
      <form v-if="editing" class="surface-card form-card case-edit-form" @submit.prevent="saveCase"><label>事项标题<input v-model="draft.title" required maxlength="300"></label><div class="form-grid"><label>分类<select v-model="draft.category"><option value="academic">教务</option><option value="award">奖助评优</option><option value="exam">考试</option><option value="competition">竞赛</option><option value="career">就业实习</option><option value="research">科研申报</option><option value="other">其他</option></select></label><label>状态<select v-model="draft.status"><option value="draft">草稿</option><option value="review">待复核</option><option value="in_progress">进行中</option><option value="completed">已完成</option><option value="archived">已归档</option></select></label></div><label>截止日期<input v-model="draft.deadline" type="date"></label><div class="button-row"><button class="button button--secondary" type="button" @click="editing=false">取消</button><button class="button button--primary" :disabled="saving">{{saving?'保存中…':'保存事项'}}</button></div></form>
      <section v-if="resources.analysis" class="review-notes" aria-label="需要核对">
        <h3>需要核对</h3><ul v-if="resources.analysis.questions?.length"><li v-for="item in [...new Set(resources.analysis.questions)]" :key="String(item)">{{item}}</li></ul>
        <p v-if="resources.analysis.review_reasons?.length">{{resources.analysis.review_reasons.join('；')}}</p>
        <details v-if="resources.analysis.summary"><summary>分析说明</summary><p>{{resources.analysis.summary}}</p></details>
      </section>
      <p v-if="resources.attachments?.missing_count" class="notice notice--warning" role="alert">还缺 {{resources.attachments.missing_count}} 项附件或读取失败，分析暂不完整。请先在下方补充附件。</p>
      <AnalysisReviewPanel v-if="account.signedIn&&!caseId.startsWith('demo-')" :key="'review-'+caseId" :case-id="caseId" :revision-key="cases.selected.updated_at" @confirmed="load"/>
      <AnalysisSection title="执行步骤" :count="resources.tasks?.length||0">
        <div v-if="resources.tasks?.length" class="compact-task-list"><article v-for="(task,index) in resources.tasks" :key="task.id"><span>{{index+1}}</span><div><strong>{{task.title}}</strong><small v-if="task.deadline">{{task.deadline}}</small></div><EvidenceLink v-if="task.evidence_ids?.length" @open="openEvidence(task)"/></article></div>
        <p v-else class="missing-copy">尚未生成有证据支撑的执行步骤。</p>
        <RouterLink class="inline-route-link" :to="`/cases/${caseId}/flow`">打开完整执行流程 <span>›</span></RouterLink>
      </AnalysisSection>
      <LocalMatchPanel :resources="cases.resources" :case-id="caseId" compact @evaluated="value=>cases.selected.relevance=value"/>
      <AttachmentPanel :key="'attachments-'+caseId" :case-id="caseId" :inventory="resources.attachments" @changed="load"/>
      <details class="surface-card result-details"><summary>材料、文件与规则 <small>{{resources.materials?.length||0}} 项材料 · {{resources.files?.length||0}} 个文件 · {{resources.rules?.length||0}} 条规则</small></summary>
      <AnalysisSection title="材料要求" :count="resources.materials?.length||0">
        <MaterialRequirementList v-if="resources.materials?.length" :items="resources.materials" @evidence="openEvidence"/>
        <p v-else class="missing-copy">未识别到有原文证据支撑的材料要求。</p>
      </AnalysisSection>
      <AnalysisSection title="已关联文件" :count="resources.files?.length||0"><div v-if="resources.files?.length" class="linked-file-list"><RouterLink v-for="file in resources.files" :key="file.id" :to="{path:'/vault',query:{case:caseId}}"><b>{{file.name}}</b><small>{{file.category}} · {{file.size}} bytes</small><span>›</span></RouterLink></div><p v-else class="missing-copy">还没有从材料库关联文件。</p><RouterLink class="inline-route-link" :to="{path:'/vault',query:{case:caseId}}">打开材料库 <span>›</span></RouterLink></AnalysisSection>
      <AnalysisSection title="规则" :count="resources.rules?.length||0">
        <div v-if="resources.rules?.length" class="rule-summary-list"><article v-for="rule in resources.rules" :key="rule.id"><div><strong>{{rule.label}}</strong><small>结论以现有画像与规则计算为准</small></div><EvidenceLink v-if="rule.evidence_ids?.length" @open="openEvidence(rule)"/></article></div>
        <p v-else class="missing-copy">尚无已确认的规则；未知不会被当作不符合。</p>
      </AnalysisSection>
      </details>
      <details v-if="account.signedIn&&!caseId.startsWith('demo-')" class="surface-card result-details"><summary>分析历史与重新分析</summary><AnalysisHistoryPanel :key="caseId" :case-id="caseId" @changed="load"/></details>
      <details class="surface-card result-details"><summary>更多核对与帮助</summary><GuideLink topic="analysis" label="如何核对结果、日期和行动步骤？"/>
      <AnalysisSection title="继续核对"><nav class="capability-links"><RouterLink :to="`/cases/${caseId}/relevance`"><b>相关性判断</b><small>查看资料与条件</small><span>›</span></RouterLink><RouterLink :to="`/cases/${caseId}/knowledge`"><b>规则依据</b><small>查看通知证据与匹配条款</small><span>›</span></RouterLink><RouterLink :to="{path:'/plan',query:{tab:'schedule',case:caseId}}"><b>安排时间</b><small>进入执行计划的日程安排</small><span>›</span></RouterLink><RouterLink :to="`/cases/${caseId}/sources`"><b>全部来源</b><small>{{resources.evidence?.length||0}} 条原文依据</small><span>›</span></RouterLink></nav></AnalysisSection>
      </details>
    </template>
    <EvidenceBottomSheet :open="evidenceOpen" :evidence="activeEvidence" @close="evidenceOpen=false"/>
  </div>
</template>

<style scoped>
.notice-overview{margin-bottom:12px;padding:20px}
.notice-overview__label{display:flex;align-items:center;justify-content:space-between;gap:12px}
.notice-overview h2{margin:12px 0;font-size:20px;line-height:1.5;overflow-wrap:anywhere}
.notice-overview__hint{color:var(--color-text-secondary);font-size:13px;margin:8px 0}
.notice-deadline{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0;padding:12px;background:var(--color-bg-soft,#f0f8f5);border-radius:12px}
.notice-deadline small{width:100%}
.review-notes{margin:12px 0;padding:12px 16px;border-left:3px solid #d6a545;border-radius:8px;background:#fff9ec;font-size:13px;line-height:1.65}
.review-notes h3{margin:0;font-size:14px}.review-notes ul{padding-left:18px;margin:6px 0}.review-notes p{margin:6px 0}
.result-details{margin:12px 0;padding:16px;min-width:0;overflow-wrap:anywhere}
.result-details>summary{cursor:pointer;font-weight:650;line-height:1.6;min-height:28px}
.result-details>summary small{display:block;font-weight:400;color:var(--color-text-secondary);margin-left:16px;font-size:12px}
.result-details :deep(.surface-card),.result-details :deep(.analysis-section){box-shadow:none;border:0;padding:12px 0;margin:0;background:transparent}
.analysis-result :deep(summary){cursor:pointer}.analysis-result :deep(summary:focus-visible){outline:2px solid var(--color-primary,#008a79);outline-offset:4px;border-radius:4px}
</style>
