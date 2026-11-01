<script setup lang="ts">
defineProps<{title:string;description?:string}>();
</script>

<template>
  <div class="section-header">
    <div><h2>{{title}}</h2><p v-if="description">{{description}}</p></div>
    <div v-if="$slots.action" class="section-header__action"><slot name="action"/></div>
  </div>
</template>
