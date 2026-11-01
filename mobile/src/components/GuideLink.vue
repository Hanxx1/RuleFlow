<script setup lang="ts">
import {computed} from 'vue';
import {RouterLink,useRoute} from 'vue-router';
import type {GuideTopic} from '../content/guide';
const props=defineProps<{topic:GuideTopic;label?:string}>();
const route=useRoute();
const target=computed(()=>({path:'/guide',query:{topic:props.topic,from:route.fullPath}}));
</script>

<template><RouterLink class="guide-context-link" :to="target"><img src="/assets/icons/status/icon_info.svg" alt=""><span>{{label||'查看操作指南'}}</span><span aria-hidden="true">›</span></RouterLink></template>

<style scoped>
.guide-context-link{display:flex;min-width:0;align-items:center;gap:8px;margin-bottom:12px;padding:10px 12px;border:1px solid #d6e9e1;border-radius:12px;background:#eef8f4;color:var(--color-primary-strong);font-size:13px;line-height:1.6}
.guide-context-link img{width:18px;height:18px;flex:none}
.guide-context-link>span:first-of-type{min-width:0;flex:1;overflow-wrap:anywhere}
</style>
