<script setup lang="ts">
import {computed} from 'vue';
const props=defineProps<{value?:string|null}>();
const normalized=computed(()=>String(props.value||'UNKNOWN').toLowerCase());
const tone=computed(()=>{
  if(['true','done','completed','active','相关'].includes(normalized.value))return 'success';
  if(['false','failed','error','不相关'].includes(normalized.value))return 'danger';
  if(['in_progress','review','processing','进行中'].includes(normalized.value))return 'info';
  if(['skipped','unknown','待确认'].includes(normalized.value))return 'warning';
  return 'neutral';
});
const label=computed(()=>({true:'相关',false:'不相关',unknown:'待确认',todo:'待完成',in_progress:'进行中',done:'已完成',skipped:'已跳过',review:'待复核',draft:'草稿',demo:'演示数据'} as Record<string,string>)[normalized.value]||String(props.value||'待确认'));
</script>

<template><span :class="['status-badge',`status-badge--${tone}`]">{{label}}</span></template>
