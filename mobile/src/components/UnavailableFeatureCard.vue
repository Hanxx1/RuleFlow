<script setup lang="ts">
defineProps<{title:string;description:string;status?:string}>();
</script>
<template><section class="unavailable-card"><div><span class="text-label">{{status||'能力说明'}}</span><h3>{{title}}</h3><p>{{description}}</p></div><slot/></section></template>
