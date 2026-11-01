<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref} from 'vue';
import {useRoute} from 'vue-router';
import AppHeader from '../../components/AppHeader.vue';
import AppState from '../../components/AppState.vue';
import ImportSourceList from './ImportSourceList.vue';
import {useImportBatchStore} from './batchStore';

const route=useRoute(),batches=useImportBatchStore(),error=ref('');
const batchId=String(route.params.id||'');let timer:number|undefined;
const terminal=computed(()=>['completed','partial_failure','failed'].includes(batches.data?.state||''));
const stateLabel=computed(()=>({draft:'等待提交',queued:'已进入分析队列',processing:'正在分析来源',completed:'分析完成',partial_failure:'部分来源处理失败',failed:'分析未完成'} as Record<string,string>)[batches.data?.state||'']||'读取中');
const sources=computed(()=>batches.data?.sources.map(source=>({id:source.id,kind:source.kind,label:source.name,detail:source.kind==='url'?String(source.metadata.final_url||source.metadata.url||'网页链接'):source.kind==='file'?String(source.metadata.mime||'文件'):`${source.metadata.characters||0} 个字符`,status:source.status,error:source.error}))||[]);
onMounted(refresh);onBeforeUnmount(()=>{if(timer)window.clearTimeout(timer)});
async function refresh(){
  if(timer)window.clearTimeout(timer);error.value='';
  try{await batches.load(batchId);if(!terminal.value)timer=window.setTimeout(refresh,450)}catch(e:any){error.value=e?.message||'分析状态读取失败'}
}
function finish(){if(batches.data?.state==='completed')batches.clearActive()}
</script>

<template>
  <div class="page page--product">
    <AppHeader title="分析进度"><template #action><RouterLink class="icon-button icon-button--plain" :to="`/imports/${batchId}/sources`" aria-label="返回来源列表">←</RouterLink></template></AppHeader>
    <div v-if="error" class="notice notice--danger dashboard-error"><span>{{error}}</span><button class="button button--small button--secondary" type="button" @click="refresh">重试</button></div>
    <AppState v-if="batches.loading&&!batches.data" kind="loading" title="正在读取分析状态"/>
    <template v-else-if="batches.data">
      <section :class="['surface-card','batch-progress-card',`batch-progress-card--${batches.data.state}`]"><span class="text-label">批次状态</span><h2>{{stateLabel}}</h2><p v-if="batches.data.state==='queued'">来源已稳定保存，正在等待进入本地分析步骤。</p><p v-else-if="batches.data.state==='processing'">正在根据成功来源建立 Evidence、规则和执行步骤。</p><p v-else-if="batches.data.state==='completed'">全部可用来源已合并为同一个事项。</p><p v-else-if="batches.data.state==='partial_failure'">成功来源已生成事项；失败来源保留错误信息，可返回处理。</p><p v-else-if="batches.data.state==='failed'">没有可用于生成事项的成功来源，请返回检查来源。</p></section>
      <section class="surface-card source-confirm-card"><div class="section-title-row"><h2>来源处理结果</h2><span class="section-count">{{batches.data.source_count}}</span></div><ImportSourceList :sources="sources" :removable="false"/></section>
      <div v-if="terminal" class="button-row"><RouterLink class="button button--secondary" :to="`/imports/${batchId}/sources`">管理来源</RouterLink><RouterLink v-if="batches.data.case_id" class="button button--primary" :to="`/cases/${batches.data.case_id}/analysis`" @click="finish">打开生成的事项</RouterLink><RouterLink v-else class="button button--primary" :to="{path:'/imports/new',query:{batch:batchId}}">补充来源</RouterLink></div>
    </template>
  </div>
</template>
