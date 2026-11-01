<script setup lang="ts">
import {ref,watch} from 'vue';
import {loadReview,submitReview,prepareLegacyReview,type AnalysisReview} from '../services/review';
const props=defineProps<{caseId:string;revisionKey?:string}>();
const emit=defineEmits<{confirmed:[]}>();
const review=ref<AnalysisReview|null>(null),loading=ref(false),saving=ref(false),error=ref('');
const actionIds=ref<string[]>([]),deadlineId=ref(''),manualDeadline=ref(''),mode=ref('none'),consent=ref(false);
const taskDates=ref<Record<string,string>>({}),taskManual=ref<Record<string,string>>({});
let requestVersion=0;
async function load(){const version=++requestVersion;review.value=null;consent.value=false;error.value='';loading.value=true;try{const value=await loadReview(props.caseId);if(version!==requestVersion)return;review.value=value;actionIds.value=value?.candidate.actions.map(item=>item.id)||[];deadlineId.value='';manualDeadline.value='';mode.value='none';taskDates.value=Object.fromEntries((value?.candidate.actions||[]).map(action=>[action.id,'inherit']));taskManual.value={}}catch(e:any){if(version===requestVersion)error.value=e.message}finally{if(version===requestVersion)loading.value=false}}
async function confirm(){if(!review.value)return;saving.value=true;error.value='';try{review.value=await submitReview(props.caseId,review.value,{actionIds:actionIds.value,deadlineId:mode.value==='candidate'?deadlineId.value:'',manualDeadline:mode.value==='manual'?manualDeadline.value:'',noDeadline:mode.value==='none',consent:consent.value,taskDeadlines:Object.fromEntries(actionIds.value.filter(id=>taskDates.value[id]&&taskDates.value[id]!=='inherit').map(id=>[id,taskDates.value[id]==='none'?{no_deadline:true}:taskDates.value[id]==='manual'?{manual_deadline:taskManual.value[id]}:{deadline_id:taskDates.value[id]}]))});emit('confirmed')}catch(e:any){error.value=e.message}finally{saving.value=false}}
async function prepare(){saving.value=true;error.value='';try{await prepareLegacyReview(props.caseId);await load()}catch(e:any){error.value=e.message}finally{saving.value=false}}
watch(()=>[props.caseId,props.revisionKey],()=>{if(props.caseId!=='demo-assessment')load()},{immediate:true});
</script>
<template>
  <section class="surface-card review-panel" aria-label="核对分析候选">
    <h2>核对分析候选</h2>
    <p v-if="loading">正在读取待核对信息…</p>
    <div v-if="error" class="notice notice--danger" role="alert">{{error}} <button type="button" class="text-button" @click="load">重新读取</button></div>
    <p v-if="review?.status==='confirmed'" role="status">日期与行动步骤已确认。资格判断仍以画像和原文条件为准。</p>
    <div v-else-if="!review&&!loading&&!error"><p>当前事项没有确认记录。可以载入已有步骤和证据进行核对，原任务ID和完成记录会保留。</p><button class="button button--secondary" type="button" :disabled="saving" @click="prepare">载入已有步骤核对</button></div>
    <form v-else-if="review" @submit.prevent="confirm">
      <p>请核对原文。这里的候选尚未进入执行计划；确认行动步骤不会将未知资格变成符合。</p>
      <fieldset>
        <legend>日期候选</legend>
        <article v-for="item in review.candidate.dates" :key="item.id" class="review-date">
          <strong>{{item.raw}}</strong>
          <small>{{({publication:'发布信息',event:'活动时间',deadline:'截止候选',unknown:'语义待核对'} as Record<string,string>)[item.role]}}</small>
          <blockquote>{{item.quote}}</blockquote>
          <p v-if="item.review_reasons.length">{{item.review_reasons.map(reason=>({missing_year:'年份缺失，请核对后填写',invalid_date:'日期无效',invalid_time:'时刻无效',unknown_date_role:'用途待核对',multiple_deadlines:'存在多个截止日期，请选择对应环节',time_requires_review:'具体时刻缺少完整年份或明确时区，请人工核对'} as Record<string,string>)[reason]||reason).join('；')}}</p>
          <label v-if="item.role==='deadline'&&item.value" class="review-choice">
            <input v-model="deadlineId" type="radio" :value="item.id" name="deadline-candidate" @change="mode='candidate'">
            <span class="review-choice__copy">采用此日期</span>
          </label>
        </article>
        <label class="review-choice">
          <input v-model="mode" type="radio" value="manual" name="deadline-mode">
          <span class="review-choice__copy">核对后填写截止日期</span>
        </label>
        <label v-if="mode==='manual'" class="review-field">
          <span>人工确认截止日期</span>
          <input v-model="manualDeadline" type="date" required aria-label="人工确认截止日期">
        </label>
        <label class="review-choice">
          <input v-model="mode" type="radio" value="none" name="deadline-mode">
          <span class="review-choice__copy">暂不设置截止日期（不会承诺截止前完成）</span>
        </label>
      </fieldset>
      <fieldset>
        <legend>选择行动步骤</legend>
        <article v-for="action in review.candidate.actions" :key="action.id" class="review-action">
          <label class="review-choice">
            <input v-model="actionIds" type="checkbox" :value="action.id">
            <span class="review-choice__copy">
              <strong>{{action.title}}</strong>
              <small v-if="action.origin==='suggestion'">建议步骤，可取消</small>
              <small v-if="action.origin==='previous'">历史步骤，请核对是否保留</small>
            </span>
          </label>
          <blockquote v-for="(quote,id) in action.evidence_quotes" :key="id">{{quote}}</blockquote>
          <label v-if="actionIds.includes(action.id)" class="review-field">
            <span>此步骤的截止日期</span>
            <select v-model="taskDates[action.id]" :aria-label="action.title+'截止日期'">
              <option value="inherit">沿用事项日期</option>
              <option value="none">暂不设置</option>
              <option v-for="date in review.candidate.dates.filter(d=>d.role==='deadline'&&d.value)" :key="date.id" :value="date.id">{{date.raw}}</option>
              <option value="manual">人工确认日期</option>
            </select>
          </label>
          <label v-if="taskDates[action.id]==='manual'" class="review-field">
            <span>人工确认步骤截止日期</span>
            <input v-model="taskManual[action.id]" type="date" required :aria-label="action.title+'人工截止日期'">
          </label>
        </article>
        <p v-if="!review.candidate.actions.length">未识别到有依据的行动步骤，不会自动补造提交任务。</p>
      </fieldset>
      <fieldset v-if="review.candidate.dependencies?.length"><legend>原文前后依赖</legend><article v-for="edge in review.candidate.dependencies" :key="edge.before_action_id+edge.after_action_id"><p>{{review.candidate.actions.find(item=>item.id===edge.before_action_id)?.title}} → {{review.candidate.actions.find(item=>item.id===edge.after_action_id)?.title}}</p><blockquote>{{edge.quote}}</blockquote></article><p>选择后续步骤时须同时选择其前置步骤。</p></fieldset>
      <label class="consent-row review-choice"><input v-model="consent" type="checkbox"><span class="review-choice__copy">我已核对所选日期与步骤及原文依赖，同意保存；资格待核对时仍需补充资料。</span></label>
      <button class="button button--primary button--block" type="submit" :disabled="saving||loading||!consent">{{saving?'正在保存…':'确认并生成行动步骤'}}</button>
    </form>
  </section>
</template>
<style scoped>
.review-panel{margin-block:16px;min-width:0;overflow-wrap:anywhere}
.review-panel h2{font-size:18px}
.review-panel form{min-width:0}
.review-panel fieldset{min-width:0;margin:16px 0;padding:12px;border:1px solid var(--color-border);border-radius:12px}
.review-panel legend{max-width:100%;padding:0 4px;font-weight:650}
.review-choice{display:flex;min-width:0;align-items:flex-start;gap:10px;margin:12px 0;line-height:1.6;cursor:pointer}
.review-choice input[type=checkbox],.review-choice input[type=radio]{margin-top:3px}
.review-choice__copy{min-width:0;flex:1;overflow-wrap:anywhere}
.review-choice__copy strong{display:block;font-weight:650}
.review-choice__copy small,.review-date>small{display:block;margin-top:3px;color:var(--color-text-secondary);font-size:12px;line-height:1.5}
.review-field{display:grid;min-width:0;gap:6px;margin:12px 0;line-height:1.5}
.review-field>input,.review-field>select{width:100%;min-width:0;max-width:100%;margin-top:0}
.review-panel blockquote{margin:8px 0;padding:8px 12px;border-left:3px solid var(--color-border);border-radius:0 8px 8px 0;background:#f4f6f8;overflow-wrap:anywhere;white-space:pre-wrap;line-height:1.65}
.review-date{padding-block:8px;border-bottom:1px solid var(--color-border)}
.review-action+.review-action{margin-top:16px;padding-top:12px;border-top:1px solid var(--color-border)}
.review-panel button{max-width:100%;white-space:normal;overflow-wrap:anywhere}
@media(max-width:390px){.review-panel{padding:14px}.review-panel fieldset{padding:10px}}
</style>
