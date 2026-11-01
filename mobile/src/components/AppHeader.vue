<script setup lang="ts">
defineProps<{title:string;subtitle?:string}>();
</script>

<template>
  <header class="app-header">
    <div class="app-header__copy">
      <h1>{{title}}</h1>
      <p v-if="subtitle">{{subtitle}}</p>
    </div>
    <div v-if="$slots.action" class="app-header__action"><slot name="action"/></div>
  </header>
</template>
