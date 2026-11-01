<script setup lang="ts">
import EvidenceLink from './EvidenceLink.vue';
defineProps<{items:any[]}>();
defineEmits<{evidence:[item:any]}>();
</script>
<template><div class="requirement-list"><article v-for="item in items" :key="item.id||item.title"><span class="requirement-list__check" aria-hidden="true">□</span><div><strong>{{item.title}}</strong><small v-if="item.state">{{item.state}}</small></div><EvidenceLink v-if="item.evidence_ids?.length" @open="$emit('evidence',item)"/></article></div></template>
