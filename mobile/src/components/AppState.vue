<script setup lang="ts">
import {computed} from 'vue';
const props=withDefaults(defineProps<{kind?:'empty'|'loading'|'offline'|'search'|'coming';title:string;description?:string;image?:string}>(),{kind:'empty'});
const imageSource=computed(()=>props.image||`/assets/illustrations/${({empty:'empty_inbox.png',search:'empty_search.png',loading:'loading_sleeping_cat.png',offline:'state_offline_satellite.png',coming:'hero_goal_mountain.png'} as Record<string,string>)[props.kind]}`);
</script>

<template>
  <div :class="['app-state',`app-state--${kind}`]">
    <img :src="imageSource" alt="" aria-hidden="true" loading="lazy" decoding="async">
    <h3>{{title}}</h3><p v-if="description">{{description}}</p><slot/>
  </div>
</template>
