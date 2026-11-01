<script setup lang="ts">
withDefaults(defineProps<{label:string;description?:string;icon:string;to?:string;disabled?:boolean}>(),{disabled:false});
</script>
<template>
  <RouterLink v-if="to&&!disabled" :to="to" class="settings-row"><span class="settings-row__icon"><img :src="icon" alt="" aria-hidden="true"></span><span class="settings-row__copy"><b>{{label}}</b><small v-if="description">{{description}}</small></span><img class="settings-row__chevron" src="/assets/icons/status/icon_chevron.svg" alt=""></RouterLink>
  <div v-else class="settings-row settings-row--disabled" aria-disabled="true"><span class="settings-row__icon"><img :src="icon" alt="" aria-hidden="true"></span><span class="settings-row__copy"><b>{{label}}</b><small>{{description||'请查看能力说明'}}</small></span><span class="coming-tag">受限</span></div>
</template>
