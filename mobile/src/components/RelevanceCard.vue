<script setup lang="ts">
import {computed} from 'vue';
import StatusBadge from './StatusBadge.vue';
const props=defineProps<{value?:string|null;facts?:any[];evaluation?:any;caseId?:string}>();
const normalized=computed(()=>String(props.value||'UNKNOWN').toUpperCase());
const reason=computed(()=>props.evaluation?.reason||null);
const labels:Record<string,string>={student_type:'身份',enrollment_year:'入学年份',college:'学院',major:'专业',class_name:'班级',rank_percent:'排名比例',team_size:'团队人数',certificate_level:'证书等级',graduation_year:'毕业年份',role:'角色',moral_bonus_items:'德育加分项目'};
const missingProfile=computed(()=>props.evaluation?.missing_profile_fields?.map((field:string)=>labels[field.replace('profile.','')]||field).join('、')||'规则所需资料');
const explanation=computed(()=>{
  if(normalized.value==='TRUE')return '现有规则与个人资料支持“相关”判断。';
  if(normalized.value==='FALSE')return '现有规则与个人资料支持“不相关”判断。';
  if(reason.value==='missing_profile_fact')return `还缺少个人画像字段：${missingProfile.value}。`;
  if(reason.value==='unmodeled_conditions')return '原文含当前画像字段无法计算的资格条件，请人工核对这些条件。';
  if(reason.value==='missing_case_fact'||reason.value==='insufficient_evidence')return '现有通知信息不足，需要核对原文中的适用条件。';
  if(reason.value==='source_failed')return '部分来源未能读取，请先修复来源后重新分析。';
  return '规则条件暂时无法计算，请核对原文和字段格式。';
});
</script>

<template>
  <section class="relevance-card"><div class="relevance-card__head"><div><span class="text-label">相关性</span><h3>这件事和我有关吗？</h3></div><StatusBadge :value="value"/></div><p>{{explanation}}</p><p v-if="evaluation?.interest_match===true&&evaluation?.interest_evidence_ids?.length">按事项分类匹配到你填写的关注偏好；资格结论保持独立。</p><p v-if="facts?.length" class="relevance-card__facts">本次判断读取了 {{facts.length}} 条账户或事项事实。</p><RouterLink v-if="normalized==='UNKNOWN'&&reason==='missing_profile_fact'" class="text-link" to="/profile">完善个人画像</RouterLink><RouterLink v-else-if="normalized==='UNKNOWN'&&caseId&&(reason==='missing_case_fact'||reason==='insufficient_evidence')" class="text-link" :to="`/cases/${caseId}/sources`">核对通知原文</RouterLink></section>
</template>
