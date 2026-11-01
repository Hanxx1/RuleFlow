<script setup lang="ts">
import {computed} from 'vue';
import StatusBadge from './StatusBadge.vue';
const props=defineProps<{item:any}>();
const category=computed(()=>({academic:'教务',award:'奖助评优',exam:'考试',competition:'竞赛',career:'就业实习',research:'科研申报',other:'其他'} as Record<string,string>)[props.item?.category]||props.item?.category||'其他');
const date=computed(()=>props.item?.deadline||'截止时间待核对');
</script>

<template>
  <RouterLink :to="`/cases/${item.id}`" class="case-card-new">
    <div class="case-card-new__top"><span class="category-pill">{{category}}</span><StatusBadge :value="item.relevance"/></div>
    <h3>{{item.title}}</h3>
    <div class="case-card-new__meta"><img src="/assets/icons/actions/icon_calendar.svg" alt=""><span>{{date}}</span></div>
    <div v-if="typeof item.progress==='number'" class="case-card-new__progress"><span><i :style="{width:`${item.progress}%`}"></i></span><small>{{item.done_task_count||0}} / {{item.task_count||0}} 步 · {{item.progress}}%</small></div>
    <div class="case-card-new__footer"><span>{{item.status==='demo'?'仅用于离线体验':'查看事项详情'}}</span><img src="/assets/icons/status/icon_chevron.svg" alt="" aria-hidden="true"></div>
  </RouterLink>
</template>
