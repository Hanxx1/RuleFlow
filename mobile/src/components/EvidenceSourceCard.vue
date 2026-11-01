<script setup lang="ts">
import type {EvidenceSource} from '../types/product';
defineProps<{source:EvidenceSource}>();
</script>
<template><article class="evidence-source-card"><span v-if="source.sourceType" class="text-label">{{source.sourceType}}</span><h3 v-if="source.title">{{source.title}}</h3><p v-if="source.quote">{{source.quote}}</p><dl><div v-if="source.publisher"><dt>发布方</dt><dd>{{source.publisher}}</dd></div><div v-if="source.effectiveDate"><dt>生效时间</dt><dd>{{source.effectiveDate}}</dd></div><div v-if="source.matchedSection"><dt>匹配章节</dt><dd>{{source.matchedSection}}</dd></div></dl><a v-if="source.url" class="text-link" :href="source.url" target="_blank" rel="noopener noreferrer">打开来源</a></article></template>
