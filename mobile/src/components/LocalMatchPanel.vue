<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref,watch} from 'vue';
import {useAccountStore} from '../stores/account';
import {loadWorkspace,emptyWorkspace} from '../services/clientWorkspace';
import {matchLocal} from '../services/localMatching';
import StatusBadge from './StatusBadge.vue';
import {profileLabels} from '../services/profileLabels';
const props=defineProps<{resources:any;caseId:string}>(),emit=defineEmits<{evaluated:[value:string]}>();
const account=useAccountStore(),data=ref(emptyWorkspace(account.user?.id||'offline')),error=ref('');
const result=computed(()=>matchLocal(props.resources||{},data.value,props.caseId));
let version=0;async function load(){const request=++version,owner=account.user?.id||'offline';data.value=emptyWorkspace(owner);try{const loaded=await loadWorkspace(owner);if(request!==version||owner!==(account.user?.id||'offline'))return;data.value=loaded;emit('evaluated',result.value.relevance)}catch(e:any){error.value=e.message}}
watch(()=>[props.caseId,props.resources,account.user?.id],load);onMounted(()=>{load();window.addEventListener('zhishi-client-changed',load)});onBeforeUnmount(()=>window.removeEventListener('zhishi-client-changed',load));
</script>
<template><section class="surface-card local-match" aria-label="本机资料关联判断"><h2>按照本机资料判断</h2><StatusBadge :value="result.relevance"/><p>读取资料版本 {{result.revision}}；只使用已确认、未过期且适用当前事项的资料。</p><p v-if="error" role="alert">{{error}}</p><p v-if="result.conflicts.length">资料冲突：{{result.conflicts.map(k=>profileLabels[k]||k).join('、')}}，相关字段按未知处理。</p><p v-if="result.missingAttachments">关键附件未齐，不能认定分析完整。</p><p v-if="result.unsupported.length">还有 {{result.unsupported.length}} 条原文条件无法计算，请核对。</p><p v-if="!result.rows.length">通知缺少可计算的有证据条件，不能据此认定相关。</p><article v-for="row in result.rows" :key="row.id"><h3>{{row.label}} · {{row.value}}</h3><p v-if="row.missing.length">请补充或核对：{{row.missing.map((k:string)=>profileLabels[k]||k).join('、')}}</p><blockquote v-for="id in row.ruleEvidence" :key="id">通知：{{resources.evidence.find((e:any)=>e.id===id)?.text}}</blockquote><blockquote v-for="a in row.profileEvidence" :key="a.id">本机资料：{{a.quote}} · {{a.scope||'通用'}}</blockquote></article><RouterLink :to="{path:'/profile',query:{case:caseId}}" class="button button--secondary">查看修改本机资料</RouterLink></section></template>
<style scoped>blockquote{margin:8px 0;overflow-wrap:anywhere}article{border-top:1px solid #ddd;padding:8px 0}</style>
