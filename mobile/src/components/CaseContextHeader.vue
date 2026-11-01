<script setup lang="ts">
import StatusBadge from './StatusBadge.vue';
defineProps<{item:any;compact?:boolean}>();
</script>

<template>
  <section :class="['case-context',{'case-context--compact':compact}]">
    <div class="case-context__top"><span v-if="item.category" class="category-pill">{{item.category}}</span><StatusBadge v-if="item.relevance" :value="item.relevance"/></div>
    <h2>{{item.title}}</h2><div v-if="item.deadline||item.status" class="case-context__meta"><span v-if="item.deadline">截止 {{item.deadline}}</span><span v-if="item.status">{{item.status}}</span><span v-if="typeof item.progress==='number'">进度 {{item.progress}}%</span></div>
  </section>
</template>
