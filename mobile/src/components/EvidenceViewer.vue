<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue';
import {boundingBox,loadEvidencePreview} from '../services/evidencePreview';
const props=defineProps<{evidence:any}>();
const url=ref(''),error=ref(''),loading=ref(false);let request=0;
const box=computed(()=>boundingBox(props.evidence));
function clear(){if(url.value)URL.revokeObjectURL(url.value);url.value=''}
async function load(){const version=++request;clear();error.value='';loading.value=false;if(!props.evidence?.document_id||!props.evidence.preview_available)return;loading.value=true;try{const blob=await loadEvidencePreview(props.evidence);if(version!==request)return;url.value=URL.createObjectURL(blob)}catch(e:any){if(version===request)error.value=e.message||'原图读取失败'}finally{if(version===request)loading.value=false}}
watch(()=>props.evidence,load,{immediate:true});onBeforeUnmount(()=>{request++;clear()});
</script>
<template><div class="evidence-viewer"><p v-if="loading" role="status">正在读取原图…</p><div v-if="error" role="alert">{{error}} <button class="text-button" type="button" @click="load">重试原图</button></div><div v-if="url" class="evidence-page"><img :src="url" alt="证据所在原文页面"><span v-if="box" class="evidence-highlight" :style="box" aria-label="原文证据高亮区域"></span></div><p v-if="url&&!box" class="capability-note">这条证据没有可靠区域坐标，请对照下方文字核对。</p><p v-if="!loading&&!url&&!error" class="capability-note">当前证据提供文字定位，暂无原图区域。</p><RouterLink v-if="evidence.document_id" :to="`/documents/${evidence.document_id}/privacy`" class="text-link">检查此文件隐私</RouterLink></div></template>
<style scoped>.evidence-viewer{min-width:0}.evidence-page{position:relative;width:100%;margin-block:12px}.evidence-page img{display:block;width:100%;height:auto}.evidence-highlight{position:absolute;border:2px solid #d27400;background:rgba(255,190,60,.22);pointer-events:none;box-sizing:border-box}</style>
