<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {Capacitor} from '@capacitor/core';
import AppHeader from '../../components/AppHeader.vue';
import GuideLink from '../../components/GuideLink.vue';
import ImportSourceCard from './ImportSourceCard.vue';
import ImportSourceList from './ImportSourceList.vue';
import {useImportDraftStore} from './draftStore';
import {useImportBatchStore} from './batchStore';
import {useAccountStore} from '../../stores/account';
import {readShared,takeSharedFiles,clearShared} from '../../core/native/share';
import {redact} from '../../services/privacy';
import {requirePrivacyReview} from '../../services/privacyGuard';
import importHero from '../../assets/illustrations/hero_multi_source_import.webp';

const route=useRoute(),router=useRouter(),draft=useImportDraftStore(),batches=useImportBatchStore(),account=useAccountStore();
const fileInput=ref<HTMLInputElement|null>(null),textArea=ref<HTMLTextAreaElement|null>(null),urlInput=ref<HTMLInputElement|null>(null);
const error=ref(''),platformNotice=ref(''),shareCount=ref(0),consent=ref(false),busy=ref(false);
const shareIds=ref<string[]>([]);let readingShared=false;
const isNative=computed(()=>Capacitor.isNativePlatform());
const targetBatchId=computed(()=>String(route.query.batch||''));
const preview=computed(()=>redact(draft.text));
const unsupportedDetection=computed(()=>preview.value.types.length>0&&preview.value.count===0);
watch(()=>[draft.text,draft.url,draft.files],()=>{consent.value=false});
async function loadShared(){if(readingShared)return;readingShared=true;
  try{
    const all=await readShared();const shared=all.filter(item=>!shareIds.value.includes(item.id));shareCount.value=all.length;
    if(shared.some(item=>item.state==='failed'))error.value='部分分享内容未读取成功（权限、体积或数量限制），请重新选择；有效项仍可核对。';
    const sharedText=shared.filter(item=>item.kind==='text').map(item=>item.text).filter(Boolean).join('\n');
    const sharedUrl=shared.find(item=>item.kind==='url'&&item.text)?.text||'';
    if(sharedText){draft.text=[draft.text,sharedText].filter(Boolean).join('\n');draft.cameFromShare=true}
    if(sharedUrl){if(!draft.url)draft.url=sharedUrl;else if(draft.url!==sharedUrl)draft.text=[draft.text,sharedUrl].filter(Boolean).join('\n')}
    if(shared.some(item=>item.kind==='file'))draft.files=[...draft.files,...await takeSharedFiles(shared)];
    shareIds.value.push(...shared.map(item=>item.id));consent.value=false;
  }catch(e:any){error.value=e?.message||'无法读取系统分享内容'}finally{readingShared=false}
}
onMounted(loadShared);watch(()=>route.query.share,loadShared);
async function focus(target:'text'|'url'){
  await nextTick();(target==='text'?textArea.value:urlInput.value)?.scrollIntoView({behavior:'smooth',block:'center'});(target==='text'?textArea.value:urlInput.value)?.focus();
}
function explainSystemShare(){platformNotice.value=isNative.value?'请从其他应用选择“分享”，再选择“知事”；返回后待确认内容会显示在这里。':'请在支持系统分享的移动端中，从其他应用选择“分享至知事”。当前浏览器可继续使用粘贴文字、网页链接和文件选择。'}
function chooseFiles(event:Event){
  error.value='';const chosen=Array.from((event.target as HTMLInputElement).files||[]);
  if(chosen.length>10){error.value='单次最多选择 10 个文件。';return}
  const allowed=new Set(['pdf','png','jpg','jpeg','txt','html','docx','xlsx','xls']);
  const unsupported=chosen.find(file=>!allowed.has(file.name.split('.').pop()?.toLowerCase()||''));
  if(unsupported){error.value=`${unsupported.name} 不是当前后端支持的文件类型。`;return}
  const tooLarge=chosen.find(file=>file.size>(/\.(png|jpe?g)$/i.test(file.name)?10:20)*1024*1024);
  if(tooLarge){error.value=`${tooLarge.name} 超过格式大小限制（图片 10 MB，其他文件 20 MB），未加入待导入来源。`;return}
  draft.files=chosen;
}
async function persistSources(){
  error.value='';
  if(!account.signedIn){error.value='保存导入来源需要先登录账户。';return}
  if(!draft.sources.length){error.value='请先粘贴文字、填写网页链接或选择文件。';return}
  if(!consent.value){error.value='请先确认来源和隐私处理范围。';return}
  busy.value=true;
  try{
    const guard=await requirePrivacyReview(draft.text,draft.files,draft.url,consent.value);
    if(guard.unchecked_sources.length&&!window.confirm(`以下来源未在端侧完成内容识别：${guard.unchecked_sources.join('、')}。请确认已人工核对敏感内容，同意发送到当前账户后端处理；这不代表内容安全。`))return;
    const batch=await batches.saveSources(targetBatchId.value||undefined,{title:draft.title,text:draft.text,url:draft.url,files:draft.files});
    if(!batch)throw Error('导入批次保存后未能重新读取');
    await clearShared(shareIds.value);shareIds.value=[];draft.reset();await router.replace(`/imports/${batch.id}/sources`);
  }catch(e:any){error.value=e?.message||'来源保存失败，请重试'}finally{busy.value=false}
}
async function discardDraft(){if(!window.confirm('清除本页尚未提交的输入和本次分享缓存？已保存到账户的来源不会删除。'))return;busy.value=true;try{await clearShared(shareIds.value);shareIds.value=[];draft.reset();consent.value=false;shareCount.value=(await readShared()).length;platformNotice.value='当前输入与本次分享缓存已清除。'}catch(e:any){error.value=e?.message||'分享缓存清理失败'}finally{busy.value=false}}
</script>

<template>
  <div class="page page--product">
    <AppHeader :title="targetBatchId?'补充导入来源':'导入通知'"><template #action><button class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></template></AppHeader>
    <GuideLink topic="import" label="导入方式、文件限制和附件处理"/>
    <div v-if="!targetBatchId&&batches.activeBatchId" class="mode-banner mode-banner--compact"><span class="mode-banner__dot"></span><div><b>有一个未结束的导入批次</b><p>已保存的来源可以继续查看或分析。</p></div><RouterLink :to="`/imports/${batches.activeBatchId}/sources`">继续</RouterLink></div>
    <section class="product-hero product-hero--import"><div><h2>各种来源，一处整理。</h2><p>文字、网页和多个文件可合并分析为同一个事项。</p></div><img :src="importHero" alt="" decoding="async"></section>
    <div v-if="error" class="notice notice--danger" role="alert">{{error}}</div><div v-if="platformNotice" class="notice notice--info">{{platformNotice}}</div>
    <section class="source-choice-grid" aria-label="导入来源">
      <ImportSourceCard title="粘贴文字" description="群聊、公告或通知正文" icon="/assets/icons/status/icon_info.svg" :active="Boolean(draft.text.trim())" @select="focus('text')"/>
      <ImportSourceCard title="上传文件" description="PDF、图片、TXT、HTML、DOCX、Excel" icon="/assets/icons/actions/icon_attach.svg" :active="Boolean(draft.files.length)" @select="fileInput?.click()"/>
      <ImportSourceCard title="网页链接" description="读取公开网页正文" icon="/assets/icons/files/file_link.svg" :active="Boolean(draft.url.trim())" @select="focus('url')"/>
      <ImportSourceCard title="从其他应用导入" :description="isNative?'接收系统分享给知事的文字、链接和文件':'在移动端通过系统分享发送至知事'" icon="/assets/icons/status/icon_external.svg" :active="shareCount>0" :status="shareCount?`${shareCount} 项待确认`:isNative?'等待系统分享':'移动端系统分享'" @select="explainSystemShare"/>
    </section>
    <section class="surface-card import-editor">
      <label v-if="!targetBatchId">事项标题 <span class="field-optional">选填</span><input v-model="draft.title" maxlength="120" placeholder="留空时由内容推断"></label>
      <label>粘贴文字<textarea ref="textArea" v-model="draft.text" rows="5" placeholder="粘贴通知、公告或转发文字"></textarea></label>
      <label>网页链接<div class="input-with-icon"><img src="/assets/icons/files/file_link.svg" alt=""><input ref="urlInput" v-model="draft.url" type="url" placeholder="https://…"></div></label>
      <label class="file-picker"><input ref="fileInput" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt,.html,.docx,.xlsx,.xls" @change="chooseFiles"><span><b>{{draft.files.length?`已选择 ${draft.files.length} 个文件`:'选择文件'}}</b><small>单次最多 10 个；图片 10 MB，其他文件 20 MB；PDF 最多 20 页</small></span></label>
    </section>
    <section v-if="draft.sources.length" class="surface-card source-confirm-card"><div class="section-title-row"><h2>准备保存的来源</h2><span class="section-count">{{draft.sources.length}}</span></div><ImportSourceList :sources="draft.sources" @remove="draft.remove"/><p>保存后来源进入当前账户批次，刷新页面仍可恢复。</p></section>
    <section v-if="draft.text" class="privacy-preview"><div class="privacy-preview__head"><img src="/assets/icons/features/icon_隐私设置.svg" alt=""><div><b>本地隐私预览</b><p>已实际遮盖 {{preview.count}} 项；识别类型：{{preview.types.join('、')||'暂无'}}</p></div></div><pre>{{preview.redacted}}</pre><p v-if="unsupportedDetection" class="privacy-warning">检测到当前规则尚不能自动遮盖的类型，请自行核对原文。</p></section>
    <label class="consent-row"><input v-model="consent" type="checkbox"><span>我已核对来源与隐私预览，同意保存到当前账户。图片、PDF和网页尚未端侧扫描，需人工核对后再发送到后端处理。</span></label>
    <div v-if="!account.signedIn" class="mode-banner"><span class="mode-banner__dot"></span><div><b>尚未登录</b><p>真实导入只进入账户空间，演示模式不会接收新数据。</p></div><RouterLink to="/auth/login">去登录</RouterLink></div>
    <button class="button button--primary button--block" type="button" :disabled="busy||!consent||!account.signedIn||!draft.sources.length" @click="persistSources">{{busy?'正在保存来源…':targetBatchId?'保存补充来源':'保存并核对来源'}}</button>
    <button v-if="draft.sources.length||shareCount" class="button button--secondary button--block" type="button" :disabled="busy" @click="discardDraft">放弃当前导入</button>
  </div>
</template>
