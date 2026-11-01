<script setup lang="ts">
import {onMounted,ref} from 'vue';
import {useAccountStore} from '../stores/account';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';

const account=useAccountStore(),form=ref({display_name:'',locale:'zh-CN',timezone:'Asia/Shanghai'}),loading=ref(false),saving=ref(false),error=ref(''),message=ref('');
onMounted(load);
async function load(){if(!account.signedIn)return;loading.value=true;try{const value=await account.loadSettings();form.value={display_name:value.display_name||'',locale:value.locale,timezone:value.timezone}}catch(e:any){error.value=e?.message||'账户设置读取失败'}finally{loading.value=false}}
async function save(){saving.value=true;error.value='';message.value='';try{await account.saveSettings({...form.value,display_name:form.value.display_name.trim()||null});message.value='账户设置已保存。'}catch(e:any){error.value=e?.message||'账户设置保存失败'}finally{saving.value=false}}
</script>

<template><div class="page page--utility"><AppHeader title="账户设置"><template #action><RouterLink class="icon-button icon-button--plain" to="/me" aria-label="返回">←</RouterLink></template></AppHeader><div v-if="error" class="notice notice--danger">{{error}}</div><div v-if="message" class="notice notice--success">{{message}}</div><AppState v-if="!account.signedIn" title="登录后管理账户设置"><RouterLink class="button button--primary" to="/auth/login">登录</RouterLink></AppState><AppState v-else-if="loading" kind="loading" title="正在读取账户设置"/><template v-else><section v-if="account.settings" class="surface-card account-summary"><span class="text-label">账户邮箱</span><strong>{{account.settings.email}}</strong><small>{{account.settings.email_verified?'邮箱已验证':'邮箱待验证'}}</small></section><form class="surface-card form-card" @submit.prevent="save"><label>显示名称<input v-model="form.display_name" maxlength="100" placeholder="如何称呼你"></label><label>语言<select v-model="form.locale"><option value="zh-CN">简体中文</option><option value="en-US">English</option></select></label><label>时区<select v-model="form.timezone"><option value="Asia/Shanghai">Asia/Shanghai</option><option value="UTC">UTC</option></select></label><button class="button button--primary button--block" :disabled="saving">{{saving?'保存中…':'保存设置'}}</button></form><RouterLink class="button button--secondary button--block" to="/auth/reset">重置密码</RouterLink><p class="capability-note">邮箱变更和账户删除不在当前设置范围内。</p></template></div></template>
