<script setup lang="ts">
import {computed,onMounted} from 'vue';
import {useRouter} from 'vue-router';
import {useAccountStore} from '../stores/account';
import AppHeader from '../components/AppHeader.vue';
import SettingsGroup from '../components/SettingsGroup.vue';
import SettingsRow from '../components/SettingsRow.vue';

const account=useAccountStore(),router=useRouter();
const identity=computed(()=>account.user?.email||'本机演示用户');
const initial=computed(()=>identity.value.trim().charAt(0).toUpperCase()||'知');
const completenessText=computed(()=>account.completeness?`当前规则资料完整度 ${account.completeness.score}%`:'用于规则资格判断，缺失原因会分别说明');
onMounted(()=>{if(account.signedIn){account.loadCompleteness();account.loadSettings()}});
async function logout(){if(!window.confirm('退出登录会清除当前账户在本机的画像、课表和课程档案。请先到个人画像导出备份；课程备份恢复预览尚未开放。确认退出？'))return;try{await account.logout()}finally{router.push('/auth/login')}}
</script>

<template>
  <div class="page page--me">
    <AppHeader title="我的">
      <template #action><RouterLink class="icon-button" to="/settings/account" aria-label="账户设置"><img src="/assets/icons/features/icon_账户设置.svg" alt=""></RouterLink></template>
    </AppHeader>
    <section class="profile-card">
      <div class="profile-avatar">{{initial}}</div><div class="profile-card__copy"><span class="text-label">{{account.signedIn?'已登录账户':'演示模式'}}</span><h2>{{identity}}</h2><p>{{account.signedIn?'你的事项与画像按账户隔离保存':'演示数据与真实账户完全隔离'}}</p></div><RouterLink v-if="!account.signedIn" class="button button--small button--primary" to="/auth/login">登录</RouterLink>
    </section>

    <SettingsGroup title="个人资料">
      <SettingsRow v-if="!account.signedIn" label="智能填表演示" description="四种校园表单 · 离线填写与导出" icon="/assets/icons/features/icon_个人画像.svg" to="/demo/forms"/>
      <SettingsRow label="个人画像" :description="completenessText" icon="/assets/icons/features/icon_个人画像.svg" to="/profile"/>
      <SettingsRow label="材料库" description="上传、分类并关联事项与步骤" icon="/assets/icons/features/icon_材料库.svg" to="/vault"/>
      <SettingsRow label="知识资料库" description="导入细则并检索可追溯条款" icon="/assets/icons/features/icon_材料库.svg" to="/knowledge"/>
    </SettingsGroup>
    <SettingsGroup title="工具与安全">
      <SettingsRow label="隐私设置" description="查看导入确认与账户数据范围" icon="/assets/icons/features/icon_隐私设置.svg" to="/settings/privacy"/>
      <SettingsRow label="登录设备" :description="account.signedIn?'查看当前账户的有效会话':'登录后可查看'" icon="/assets/icons/features/icon_登录设备.svg" to="/settings/devices"/>
    </SettingsGroup>
    <SettingsGroup title="账户与支持">
      <SettingsRow label="账户设置" :description="account.settings?.display_name||'管理显示名称、语言和时区'" icon="/assets/icons/features/icon_账户设置.svg" to="/settings/account"/>
      <SettingsRow label="使用指南" description="完整操作步骤、结果说明与常见问题" icon="/assets/icons/features/icon_使用指南.svg" to="/guide?from=/me"/>
      <SettingsRow label="帮助与反馈" description="查看使用说明并复制诊断信息" icon="/assets/icons/features/icon_帮助反馈.svg" to="/help"/>
      <SettingsRow label="关于知事" description="产品信息与隐私说明" icon="/assets/icons/features/icon_关于.svg" to="/about"/>
    </SettingsGroup>
    <button v-if="account.signedIn" class="button button--danger button--block" type="button" @click="logout">退出登录</button>
  </div>
</template>
