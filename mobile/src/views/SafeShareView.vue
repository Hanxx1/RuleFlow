<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import AppHeader from '../components/AppHeader.vue';
import GuideLink from '../components/GuideLink.vue';
import AppState from '../components/AppState.vue';
import CaseContextHeader from '../components/CaseContextHeader.vue';
import ImportSourceCard from '../components/ImportSourceCard.vue';
import {useCasesStore} from '../stores/cases';
import {analyzePrivacy,type PrivacyAnalysis} from '../services/privacy';
import safeHero from '../assets/illustrations/hero_safe_share.webp';
import safeEmpty from '../assets/illustrations/empty_privacy_safe.webp';

const route=useRoute(),router=useRouter(),cases=useCasesStore();
const error=ref(''),message=ref(''),text=ref(''),result=ref<PrivacyAnalysis|null>(null),checking=ref(false),fileInput=ref<HTMLInputElement|null>(null),textArea=ref<HTMLTextAreaElement|null>(null);
const contextId=computed(()=>String(route.query.case||''));
const hasContext=computed(()=>Boolean(contextId.value&&cases.selected?.id===contextId.value));
const unsupportedLabels:Record<string,string>={email:'邮箱',student_id:'疑似学号',name:'姓名',address:'地址'};
const unsupported=computed(()=>result.value?.unsupported_types.map(type=>unsupportedLabels[type]||type)||[]);
const hasSafeVersion=computed(()=>Boolean(result.value?.findings.length)&&!unsupported.value.length&&result.value?.redacted_text!==text.value);
onMounted(loadContext);watch(contextId,loadContext);watch(text,()=>{result.value=null});
async function loadContext(){
  if(!contextId.value)return;
  error.value='';
  try{await cases.loadOne(contextId.value);await cases.loadResources(contextId.value);const source=cases.resources?.evidence?.[0];if(source?.text){text.value=source.text;message.value='已载入当前事项的第一条原文依据，请确认后开始检查。'}else message.value='当前事项没有可带入的原文依据。'}catch(e:any){error.value=e?.message||'事项内容读取失败'}
}
function focusText(){textArea.value?.focus();textArea.value?.scrollIntoView({behavior:'smooth',block:'center'})}
async function chooseFile(event:Event){
  error.value='';message.value='';const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;
  if(file.size>20*1024*1024){error.value='文件超过 20 MB，未读取。';return}
  if(file.type!=='text/plain'&&!file.name.toLowerCase().endsWith('.txt')){error.value='当前文件入口支持 TXT；其他格式可先复制文字后检查。';return}
  try{text.value=await file.text();message.value=`已读取 ${file.name}，请开始隐私检查。`}catch{error.value='文件读取失败，请改为粘贴文字。'}
}
async function analyze(){if(!text.value.trim())return;checking.value=true;error.value='';message.value='';try{result.value=await analyzePrivacy(text.value);message.value=`检查完成，共发现 ${result.value.findings.length} 项已支持的敏感格式。`}catch(e:any){error.value=e?.message||'隐私检查失败'}finally{checking.value=false}}
async function copy(){if(!hasSafeVersion.value||!result.value)return;try{await navigator.clipboard.writeText(result.value.redacted_text);message.value='安全版本已复制。'}catch{error.value='复制失败，请检查浏览器剪贴板权限。'}}
async function share(){if(!hasSafeVersion.value||!result.value)return;if(!navigator.share){error.value='当前平台不支持系统分享，请使用复制。';return}try{await navigator.share({title:hasContext.value?cases.selected.title:'知事隐私保护',text:result.value.redacted_text})}catch(e:any){if(e?.name!=='AbortError')error.value='系统分享未完成。'}}
</script>

<template>
  <div class="page page--product page--privacy">
    <AppHeader title="隐私保护"><template #action><button class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></template></AppHeader>
    <GuideLink topic="privacy" label="检测范围与安全分享操作说明"/>
    <div v-if="error" class="notice notice--danger" role="alert">{{error}}</div><div v-if="message" class="notice notice--success">{{message}}</div>
    <AppState v-if="contextId&&cases.loading&&!hasContext" kind="loading" title="正在读取事项原文"/>
    <template v-else>
      <section class="product-hero product-hero--privacy"><div><h2>分享前，先检查一下。</h2><p>识别并遮盖身份证号、手机号和银行卡号；结果仍需人工核对。</p></div><img :src="safeHero" alt="" decoding="async"></section>
      <CaseContextHeader v-if="hasContext" :item="cases.selected" compact/>
      <section class="privacy-source-grid" aria-label="内容来源"><ImportSourceCard title="粘贴文字" description="从剪贴板粘贴需要检查的内容" icon="/assets/icons/status/icon_info.svg" :active="Boolean(text.trim())" @select="focusText"/><ImportSourceCard title="选择文件" description="读取 TXT 文件中的文字" icon="/assets/icons/actions/icon_attach.svg" @select="fileInput?.click()"/><input ref="fileInput" class="visually-hidden" type="file" accept=".txt,text/plain" @change="chooseFile"></section>
      <section class="analysis-section privacy-workbench"><header><h2>待检查文本</h2><button v-if="hasContext" class="text-link text-button" type="button" @click="loadContext">重新载入事项原文</button></header><textarea ref="textArea" v-model="text" rows="7" placeholder="粘贴需要分享的文本"></textarea><button class="button button--primary button--block" type="button" :disabled="checking||!text.trim()" @click="analyze">{{checking?'检查中…':'开始隐私检查'}}</button><p class="capability-note">检查内容不会保存到个人资料、事项或检测历史中。</p></section>
      <AppState v-if="!text.trim()" :image="safeEmpty" title="暂无可检查文本" description="粘贴文字、选择 TXT 文件，或从具体事项的“安全分享”入口带入原文。"/>
      <section v-else-if="result" class="analysis-section"><header><h2>隐私检测结果</h2><span class="section-count">{{result.findings.length}}</span></header><div v-if="result.findings.length" class="finding-list"><span v-for="finding in result.findings" :key="finding.id">{{finding.label}} · 位置 {{finding.start}}–{{finding.end}}</span></div><div v-if="unsupported.length" class="notice notice--warning">检测到 {{unsupported.join('、')}}，当前规则不能可靠遮盖，请手动处理后再分享。</div><div v-if="!result.findings.length" class="privacy-safe-message"><b>当前规则未发现已支持的敏感格式</b><p>这不是“绝对安全”保证，请继续核对姓名、地址和上下文。</p></div><div v-else class="redaction-preview"><section><span class="text-label">原文</span><pre>{{text}}</pre></section><section><span class="text-label">安全版本</span><pre>{{result.redacted_text}}</pre></section></div><div class="button-row"><button class="button button--secondary" type="button" :disabled="!hasSafeVersion" @click="copy">复制安全版本</button><button class="button button--primary" type="button" :disabled="!hasSafeVersion" @click="share">安全分享</button></div><p v-if="result.findings.length&&!hasSafeVersion" class="capability-note">请先手动处理未支持的敏感格式。</p></section>
    </template>
  </div>
</template>
