<script setup lang="ts">
defineProps<{title:string;count?:number}>();
</script>

<template>
  <section class="analysis-section"><header><h2>{{title}}</h2><span v-if="count!==undefined" class="section-count">{{count}}</span></header><slot/></section>
</template>
