<script setup lang="ts">
withDefaults(defineProps<{label:string;icon:string;to?:string;disabled?:boolean;hint?:string}>(),{disabled:false});
</script>

<template>
  <RouterLink v-if="to&&!disabled" :to="to" class="feature-shortcut">
    <span class="feature-shortcut__icon"><img :src="icon" alt="" aria-hidden="true"></span>
    <span class="feature-shortcut__label">{{label}}</span>
    <small v-if="hint">{{hint}}</small>
  </RouterLink>
  <div v-else class="feature-shortcut feature-shortcut--disabled" aria-disabled="true">
    <span class="feature-shortcut__icon"><img :src="icon" alt="" aria-hidden="true"></span>
    <span class="feature-shortcut__label">{{label}}</span>
    <small>{{hint||'即将支持'}}</small>
  </div>
</template>
