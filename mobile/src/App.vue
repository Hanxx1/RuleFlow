<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,watch} from 'vue';
import {RouterView,useRoute,useRouter} from 'vue-router';
import {useAccountStore} from './stores/account';
import {useCasesStore} from './stores/cases';
import {useDashboardStore} from './stores/dashboard';
import BottomNav from './components/BottomNav.vue';
import {readShared,subscribeShared} from './services/share';

const account=useAccountStore(),cases=useCasesStore(),dashboard=useDashboardStore();watch(()=>account.user?.id,()=>{cases.$reset();dashboard.$reset()});
const route=useRoute();
const router=useRouter();let sharedListener:{remove:()=>Promise<void>}|undefined,closed=false;
async function showShared(){try{if((await readShared()).length&&!closed)await router.push({path:'/imports/new',query:{share:String(Date.now())}})}catch{/* Import screen exposes read errors when opened manually. */}}
onMounted(async()=>{sharedListener=await subscribeShared(showShared);if(closed){await sharedListener.remove();return}await router.isReady();await showShared()});
onBeforeUnmount(()=>{closed=true;sharedListener?.remove()});
const showNav=computed(()=>!route.path.startsWith('/auth/')&&route.path!=='/welcome');
</script>

<template>
  <main :class="['app-shell',{'app-shell--with-nav':showNav}]">
    <RouterView v-slot="{Component}"><Transition name="page-fade" mode="out-in"><component :is="Component"/></Transition></RouterView>
    <BottomNav v-if="showNav"/>
  </main>
</template>
