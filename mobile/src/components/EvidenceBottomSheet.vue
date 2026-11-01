<script setup lang="ts">
import AppBottomSheet from './AppBottomSheet.vue';
import EvidenceViewer from './EvidenceViewer.vue';
defineProps<{open:boolean;evidence:any|null}>();
defineEmits<{close:[]}>();
</script>
<template><AppBottomSheet :open="open" title="原文依据" @close="$emit('close')"><div v-if="evidence" class="evidence-sheet"><dl><div v-if="evidence.source_name"><dt>来源</dt><dd>{{evidence.source_name}}</dd></div><div v-if="evidence.locator"><dt>位置</dt><dd>{{evidence.locator}}</dd></div><div v-if="evidence.page!==null&&evidence.page!==undefined"><dt>页码</dt><dd>{{evidence.page}}</dd></div></dl><EvidenceViewer :evidence="evidence"/><blockquote>{{evidence.text||evidence.quote}}</blockquote><small v-if="evidence.id">EvidenceRef · {{evidence.id}}</small></div></AppBottomSheet></template>
