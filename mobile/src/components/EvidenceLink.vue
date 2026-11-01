<script setup lang="ts">
defineProps<{label?:string}>();
defineEmits<{open:[]}>();
</script>
<template><button class="evidence-link" type="button" @click="$emit('open')"><span>{{label||'查看依据'}}</span><span aria-hidden="true">›</span></button></template>
