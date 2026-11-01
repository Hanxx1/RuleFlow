<script setup lang="ts">
defineProps<{title:string;description:string;icon:string;active?:boolean;disabled?:boolean;status?:string}>();
defineEmits<{select:[]}>();
</script>

<template>
  <button :class="['import-source-card',{active,disabled}]" type="button" :disabled="disabled" @click="$emit('select')">
    <span class="import-source-card__icon"><img :src="icon" alt=""></span><span class="import-source-card__copy"><strong>{{title}}</strong><small>{{description}}</small></span><span v-if="status" class="import-source-card__status">{{status}}</span><span v-else aria-hidden="true">›</span>
  </button>
</template>
