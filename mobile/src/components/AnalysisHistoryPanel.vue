<script setup lang="ts">
import {ref,watch} from 'vue';
import {api} from '../services/api';
const props=defineProps<{caseId:string}>();
const emit=defineEmits<{changed:[]}>();
const versions=ref<any[]>([]),inputs=ref<any[]>([]),busy=ref(false),error=ref(''),consent=ref(false),message=ref('');
let generation=0;
async function load(){const current=++generation;error.value='';consent.value=false;try{const [history,sources]=await Promise.all([api(`/api/v1/cases/${props.caseId}/analysis-history`),api(`/api/v1/cases/${props.caseId}/analysis-inputs`)]);if(current===generation){versions.value=Array.isArray(history)?history:[];inputs.value=Array.isArray(sources)?sources:[]}}catch(e:any){if(current===generation)error.value=e.message}}
async function retry(importId:string){if(!consent.value)return;busy.value=true;error.value='';message.value='';try{const result=await api(`/api/v1/imports/${importId}/retry`,{method:'POST',body:JSON.stringify({consent:true})});message.value=result.state==='cancelled'?'重新分析已取消。':'已完成重新分析，请重新核对当前候选。';await load();emit('changed')}catch(e:any){error.value=e.message}finally{busy.value=false;consent.value=false}}
watch(()=>props.caseId,()=>{versions.value=[];inputs.value=[];load()},{immediate:true});
</script>
<template>
  <section class="surface-card" aria-label="分析版本与重试">
    <h2>分析版本与重试</h2><p>历史快照仅用于追溯。重新分析保留原证据与已有步骤，当前候选须再次确认；旧规则不会自动删除。</p>
    <p v-if="error" class="notice notice--danger" role="alert">{{error}} <button type="button" @click="load">重新读取历史</button></p><p v-if="message" role="status">{{message}}</p>
    <details v-for="version in versions" :key="version.revision"><summary>分析版本 {{version.revision}} · {{version.created_at}}</summary><p>{{version.candidate.analysis_mode}} · {{version.candidate.schema_version}}</p><p v-for="action in version.candidate.actions" :key="action.id">{{action.title}}</p><blockquote v-for="date in version.candidate.dates" :key="date.id">{{date.quote}}</blockquote></details>
    <template v-if="inputs.length"><label class="consent-row"><input v-model="consent" type="checkbox" :disabled="busy">我同意使用已保存证据重新分析，并重新核对结果。</label><button v-for="input in inputs" :key="input.import_id" class="button button--secondary" :disabled="busy||!consent" @click="retry(input.import_id)">{{busy?'分析中…':'重新分析：'+input.name}}</button></template>
  </section>
</template>
<style scoped>section{margin-block:16px;overflow-wrap:anywhere}details{margin-block:12px}blockquote{margin:8px 0;padding:8px;background:#f4f6f8}button{margin-block:6px;max-width:100%;white-space:normal}</style>
