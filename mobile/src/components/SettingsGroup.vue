<script setup lang="ts">defineProps<{title:string}>();</script>
<template><section class="settings-group"><h2>{{title}}</h2><div class="settings-group__card"><slot/></div></section></template>
