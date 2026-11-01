<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import ImportSourceList from '../components/ImportSourceList.vue';
import {useImportBatchStore} from '../stores/importBatch';
import {api} from '../services/api';

const route=useRoute(),router=useRouter(),batches=useImportBatchStore();
const error=ref(''),busy=ref(false);
const batchId=computed(()=>String(route.params.id||batches.activeBatchId||''));
const sources=computed(()=>batches.data?.sources.map(source=>({id:source.id,kind:source.kind,label:source.name,detail:source.kind==='file'?`${source.metadata.mime||'文件'} · ${formatBytes(Number(source.metadata.size||0))}`:source.kind==='url'?String(source.metadata.final_url||source.metadata.url||'网页链接'):`${source.metadata.characters||0} 个字符`,status:source.status,error:source.error,removable:batches.data?.state==='draft'||source.status==='failed'}))||[]);
const analyzableCount=computed(()=>batches.data?.sources.filter(source=>source.status==='ready'||source.status==='completed').length||0);
const allFailed=computed(()=>Boolean(batches.data?.source_count&&!analyzableCount.value));
onMounted(load);
async function load(){
  if(!batchId.value)return;
  if(!route.params.id){await router.replace(`/imports/${batchId.value}/sources`);return}
  try{await batches.load(batchId.value)}catch(e:any){error.value=e?.message||'导入批次读取失败'}
}
async function remove(sourceId:string){busy.value=true;error.value='';try{await batches.removeSource(batchId.value,sourceId)}catch(e:any){error.value=e?.message||'来源删除失败'}finally{busy.value=false}}
async function analyze(){busy.value=true;error.value='';try{await batches.analyze(batchId.value);await router.push(`/imports/${batchId.value}/progress`)}catch(e:any){error.value=e?.message||'分析启动失败'}finally{busy.value=false}}
async function importAttachment(sourceId:string,index:number){if(!window.confirm('该附件尚未在端侧扫描。确认已核对链接和隐私范围，同意获取并保存到当前账户后端？'))return;busy.value=true;error.value='';try{await api(`/api/v1/import-batches/${batchId.value}/sources/${sourceId}/attachments`,{method:'POST',body:JSON.stringify({index,consent:true})});await load()}catch(e:any){error.value=e?.message||'附件获取失败'}finally{busy.value=false}}
function formatBytes(value:number){if(!value)return '已提取文本';if(value<1024)return `${value} B`;if(value<1024*1024)return `${(value/1024).toFixed(1)} KB`;return `${(value/1024/1024).toFixed(1)} MB`}
function attachmentList(metadata:Record<string,unknown>):{url:string;title:string}[]{return Array.isArray(metadata.attachments)?metadata.attachments.filter(item=>item&&typeof item.url==='string'&&typeof item.title==='string'):[]}
</script>

<template>
  <div class="page page--product">
    <AppHeader title="确认导入来源"><template #action><RouterLink class="icon-button icon-button--plain" to="/imports/new" aria-label="返回导入通知">←</RouterLink></template></AppHeader>
    <div v-if="error" class="notice notice--danger" role="alert">{{error}}</div>
    <AppState v-if="batches.loading&&!batches.data" kind="loading" title="正在恢复导入批次"/>
    <AppState v-else-if="!batchId" title="没有进行中的导入批次" description="选择文字、网页或文件后，会创建一个可恢复的导入批次。"><RouterLink class="button button--primary" to="/imports/new">选择来源</RouterLink></AppState>
    <template v-else-if="batches.data">
      <section class="surface-card source-confirm-card"><div class="section-title-row"><div><span class="text-label">{{batches.data.title||'待分析通知'}}</span><h2>已保存 {{batches.data.source_count}} 个来源</h2></div><span class="section-count">{{batches.data.source_count}}</span></div><ImportSourceList :sources="sources" @remove="remove"/><p>每个来源独立记录处理结果；失败来源不会阻止其余内容生成事项。</p></section>
      <div v-if="allFailed" class="notice notice--danger">全部来源均处理失败，没有内容可以参与分析。请删除失败来源后重试，或补充新的文字、链接或文件。</div>
      <section v-if="batches.data.can_add_sources&&batches.data.sources.some(source=>attachmentList(source.metadata).length)" class="surface-card"><h2>网页附件候选</h2><p>仅发现链接，尚未获取附件；每项须单独核对。</p><template v-for="source in batches.data.sources" :key="source.id"><article v-for="(attachment,index) in attachmentList(source.metadata)" :key="attachment.url"><b>{{attachment.title}}</b><p style="overflow-wrap:anywhere">{{attachment.url}}</p><button class="button button--secondary" :disabled="busy" @click="importAttachment(source.id,Number(index))">确认获取此附件</button></article></template></section>
      <div v-else-if="batches.data.failed_source_count" class="notice notice--warning">有 {{batches.data.failed_source_count}} 个来源处理失败且不会参与分析；其余 {{analyzableCount}} 个来源可以继续生成事项。</div>
      <AppState v-if="!batches.data.source_count" title="批次中还没有来源" description="补充至少一个来源后再开始分析。"/>
      <div v-if="batches.data.state==='draft'&&allFailed" class="button-row"><button class="button button--secondary" type="button" :disabled="busy" @click="analyze">{{busy?'正在记录…':'结束并查看失败原因'}}</button><RouterLink class="button button--primary" :to="{path:'/imports/new',query:{batch:batchId}}">补充可用来源</RouterLink></div>
      <div v-else class="button-row"><RouterLink v-if="batches.data.can_add_sources" class="button button--secondary" :to="{path:'/imports/new',query:{batch:batchId}}">补充来源</RouterLink><button v-if="batches.data.state==='draft'" class="button button--primary" type="button" :disabled="busy||!analyzableCount" @click="analyze">{{busy?'正在启动…':batches.data.failed_source_count?'开始部分分析':'开始分析'}}</button><RouterLink v-else class="button button--primary" :to="`/imports/${batchId}/progress`">查看分析状态</RouterLink></div>
    </template>
  </div>
</template>
