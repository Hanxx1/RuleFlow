<script setup lang="ts">
import {onMounted,ref} from 'vue';
import {useAccountStore} from '../stores/account';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import StatusBadge from '../components/StatusBadge.vue';

const account=useAccountStore(),loading=ref(false),error=ref(''),message=ref(''),revoking=ref('');
onMounted(load);
async function load(){if(!account.signedIn)return;loading.value=true;try{await account.loadDevices()}catch(e:any){error.value=e?.message||'设备列表读取失败'}finally{loading.value=false}}
async function revoke(id:string){revoking.value=id;error.value='';message.value='';try{await account.revokeDevice(id);message.value='该设备会话已撤销；如果这是当前设备，请重新登录。'}catch(e:any){error.value=e?.message||'设备撤销失败'}finally{revoking.value=''}}
</script>

<template><div class="page page--utility"><AppHeader title="登录设备"><template #action><RouterLink class="icon-button icon-button--plain" to="/me" aria-label="返回">←</RouterLink></template></AppHeader><div v-if="error" class="notice notice--danger">{{error}}</div><div v-if="message" class="notice notice--success">{{message}}</div><AppState v-if="!account.signedIn" title="登录后查看设备"><RouterLink class="button button--primary" to="/auth/login">登录</RouterLink></AppState><AppState v-else-if="loading" kind="loading" title="正在读取登录设备"/><div v-else class="resource-list"><article v-for="item in account.devices" :key="item.id" class="surface-card device-card"><span class="device-card__icon"><img src="/assets/icons/features/icon_登录设备.svg" alt=""></span><div><h3>{{item.device_name||'未命名设备'}}</h3><p>最近活动 {{item.last_used_at||item.created_at}}</p></div><StatusBadge value="active"/><button class="button button--small button--danger" type="button" :disabled="revoking===item.id" @click="revoke(item.id)">{{revoking===item.id?'撤销中…':'撤销'}}</button></article><AppState v-if="!account.devices.length" title="没有有效设备会话"/></div></div></template>
