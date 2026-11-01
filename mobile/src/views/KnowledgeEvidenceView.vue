<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {api} from '../services/api';
import {useAccountStore} from '../stores/account';
import {useCasesStore} from '../stores/cases';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import CaseContextHeader from '../components/CaseContextHeader.vue';
import EvidenceLink from '../components/EvidenceLink.vue';
import EvidenceBottomSheet from '../components/EvidenceBottomSheet.vue';
import knowledgeHero from '../assets/illustrations/hero_knowledge_evidence.webp';

const route=useRoute(),router=useRouter(),account=useAccountStore(),cases=useCasesStore();
const error=ref(''),loading=ref(false),knowledge=ref<any>(null),open=ref(false),active=ref<any>(null);
const id=computed(()=>String(route.params.id));
onMounted(load);
async function load(){loading.value=true;error.value='';try{await cases.loadOne(id.value);await cases.loadResources(id.value);if(account.signedIn&&!id.value.startsWith('demo-'))knowledge.value=await api(`/api/v1/cases/${id.value}/knowledge-evidence`)}catch(e:any){error.value=e?.message||'规则依据读取失败'}finally{loading.value=false}}
function show(rule:any){active.value=cases.resources?.evidence?.find((item:any)=>item.id===rule.evidence_ids?.[0])||null;open.value=Boolean(active.value)}
function score(value:number|null){return value==null?'—':`${Math.round(value*100)}%`}
async function attach(item:any){if(!window.confirm('确认此条款适用于当前事项？关联后将重新核对资格，并要求重新确认行动步骤。'))return;try{await api(`/api/v1/cases/${id.value}/knowledge/${item.id}/attach`,{method:'POST',body:JSON.stringify({consent:true})});await load()}catch(e:any){error.value=e.message}}
</script>

<template><div class="page page--product"><AppHeader title="规则依据"><template #action><button class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></template></AppHeader><div v-if="error" class="notice notice--danger">{{error}}</div><AppState v-if="loading&&!cases.selected" kind="loading" title="正在读取规则依据"/><template v-else-if="cases.selected"><section class="product-hero product-hero--knowledge"><div><h2>每条判断，都应该回到原文。</h2><p>同时查看通知内证据与可追溯的知识条款。</p></div><img :src="knowledgeHero" alt="" loading="lazy" decoding="async"></section><CaseContextHeader :item="cases.selected" compact/><section class="analysis-section"><header><h2>当前通知依据</h2><span class="section-count">{{cases.resources?.rules?.length||0}}</span></header><div v-if="cases.resources?.rules?.length" class="rule-summary-list"><article v-for="rule in cases.resources.rules" :key="rule.id"><div><strong>{{rule.label}}</strong><small>{{rule.evidence_ids?.length||0}} 条原文引用</small></div><EvidenceLink v-if="rule.evidence_ids?.length" @open="show(rule)"/></article></div><p v-else class="missing-copy">当前通知没有返回已确认规则。</p></section><RouterLink class="button button--secondary" to="/knowledge">管理知识资料</RouterLink><section class="analysis-section"><header><h2>知识条款</h2><span class="section-count">{{knowledge?.items?.length||0}}</span></header><AppState v-if="!account.signedIn" title="登录后查看知识条款" description="知识检索基于账户事项，不会混入离线样例。"/><AppState v-else-if="knowledge?.status==='unavailable'" title="当前环境未配置知识来源" description="通知内 Evidence 仍可正常查看；配置正式 Provider 后会使用同一接口返回条款。"/><AppState v-else-if="knowledge&&!knowledge.items.length" title="没有匹配到相关条款" description="可以继续依据当前通知原文核对。"/><div v-else class="knowledge-list"><article v-for="item in knowledge?.items||[]" :key="item.id" class="evidence-source-card"><span class="text-label">{{item.publisher}}</span><h3>{{item.title}}</h3><button v-if="item.match_type==='local_tfidf_bigram'" class="button button--small button--secondary" type="button" @click="attach(item)">核对并关联条款</button><strong>{{item.matched_section}}</strong><blockquote>{{item.quote}}</blockquote><dl><div><dt>生效时间</dt><dd>{{item.effective_date||'未注明'}}</dd></div><div><dt>匹配方式</dt><dd>{{item.match_type}} · {{score(item.match_score)}}</dd></div><div><dt>置信度</dt><dd>{{item.confidence==null?'未提供概率置信度':item.confidence}}</dd></div><div><dt>引用定位</dt><dd>{{item.reference?.locator}}</dd></div></dl><small v-if="item.evidence_ids?.length">关联 EvidenceRef：{{item.evidence_ids.join('、')}}</small><a v-if="item.url" class="text-link" :href="item.url" target="_blank" rel="noopener noreferrer">打开来源</a></article></div></section></template><EvidenceBottomSheet :open="open" :evidence="active" @close="open=false"/></div></template>
