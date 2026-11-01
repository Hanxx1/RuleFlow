<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import CaseContextHeader from '../components/CaseContextHeader.vue';
import LocalMatchPanel from '../components/LocalMatchPanel.vue';
import {useCasesStore} from '../features/cases/store';
import relevanceHero from '../assets/illustrations/hero_profile_relevance.webp';
const route=useRoute(),router=useRouter(),cases=useCasesStore(),error=ref('');
const id=computed(()=>String(route.params.id));
onMounted(async()=>{try{await cases.loadOne(id.value);await cases.loadResources(id.value)}catch(e:any){error.value=e?.message||'相关性结果读取失败'}});
</script>
<template><div class="page page--product"><AppHeader title="相关性判断"><template #action><button class="icon-button icon-button--plain" type="button" aria-label="返回" @click="router.back()">←</button></template></AppHeader><div v-if="error" class="notice notice--danger">{{error}}</div><AppState v-if="cases.loading&&!cases.selected" kind="loading" title="正在读取判断依据"/><template v-else-if="cases.selected"><section class="product-hero product-hero--relevance"><div><h2>资料与通知条件，逐项对照。</h2><p>通知条件与当前设备已确认资料逐项比对，服务端旧画像不参与本次判断。</p></div><img :src="relevanceHero" alt="" decoding="async"></section><CaseContextHeader :item="cases.selected" compact/><LocalMatchPanel :resources="cases.resources" :case-id="id" @evaluated="value=>cases.selected.relevance=value"/></template></div></template>
