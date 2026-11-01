<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {useAccountStore} from '../stores/account';
import {useCasesStore} from '../features/cases/store';
import {useDashboardStore} from '../stores/dashboard';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import CaseCard from '../components/CaseCard.vue';
import FeatureShortcut from '../components/FeatureShortcut.vue';
import HeroCard from '../components/HeroCard.vue';
import SectionHeader from '../components/SectionHeader.vue';
import TaskTimeline from '../components/TaskTimeline.vue';
import AppBottomSheet from '../components/AppBottomSheet.vue';
import {quickStart} from '../content/guide';

const account=useAccountStore(),cases=useCasesStore(),dashboard=useDashboardStore();
const guideOpen=ref(false),guideStep=ref(0);
const guide=quickStart;
const recentCases=computed(()=>account.signedIn?(dashboard.data?.recent_cases||[]):cases.items.slice(0,4));
const todayTasks=computed(()=>dashboard.data?.today_tasks.map(task=>({...task,display_time:task.scheduled_start?`今日 ${new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:dashboard.data?.timezone||'Asia/Shanghai'}).format(new Date(task.scheduled_start))}`:(task.deadline?'今日截止':null)}))||[]);
const stats=computed(()=>dashboard.data?[['全部事项',dashboard.data.total_cases,'all'],['进行中',dashboard.data.in_progress_cases,'in_progress'],['即将截止',dashboard.data.due_soon_cases,'due_soon'],['已完成',dashboard.data.completed_cases,'completed']]:[]);
onMounted(loadHome);
async function loadHome(){try{if(account.signedIn)await dashboard.load();else await cases.load()}catch{/* store 保留可重试错误 */}}
async function changeTask(id:string,status:string){try{await dashboard.setTask(id,status)}catch{/* store 保留可重试错误 */}}
function nextGuide(){if(guideStep.value<guide.length-1)guideStep.value++;else closeGuide()}
function openGuide(){guideStep.value=0;guideOpen.value=true}
function closeGuide(){guideOpen.value=false;localStorage.setItem('zhishi-onboarding-complete','1')}
</script>

<template>
  <div class="page page--home">
    <AppHeader title="知事" subtitle="让每一条通知，都变成清晰的行动">
      <template #action><RouterLink class="icon-button" to="/help" aria-label="帮助与说明"><img src="/assets/icons/status/icon_info.svg" alt=""></RouterLink></template>
    </AppHeader>

    <div v-if="!account.signedIn" class="mode-banner"><span class="mode-banner__dot"></span><div><b>演示模式</b><p>当前只展示明确标记的离线样例，不会混入账户数据。</p></div><RouterLink to="/auth/login">登录</RouterLink></div>

    <HeroCard title="把通知交给我，剩下的交给知事。" description="自动解析通知，整理事项、规则与执行步骤。" image="/assets/illustrations/hero_notice_checklist.png">
      <RouterLink class="button button--hero" to="/imports/new">导入并分析</RouterLink>
    </HeroCard>

    <section v-if="account.signedIn&&stats.length" class="dashboard-stats" aria-label="事项统计">
      <RouterLink v-for="([label,value,filter]) in stats" :key="String(filter)" :to="{path:'/cases',query:{status:filter}}" class="dashboard-stat"><strong>{{value}}</strong><span>{{label}}</span></RouterLink>
    </section>

    <section class="shortcut-grid" aria-label="常用功能">
      <FeatureShortcut label="我的事项" icon="/assets/icons/features/icon_我的事项.svg" to="/cases" hint="查看全部事项"/>
      <FeatureShortcut label="材料库" icon="/assets/icons/features/icon_材料库.svg" to="/vault" hint="分类与关联材料"/>
      <FeatureShortcut label="使用指南" icon="/assets/icons/features/icon_使用指南.svg" to="/guide?from=/home" hint="完整流程与常见问题"/>
      <FeatureShortcut label="常见问题" icon="/assets/icons/features/icon_常见问题.svg" to="/help" hint="查看说明"/>
    </section>
    <p class="home-guide-entry">第一次使用？<button type="button" @click="openGuide">查看四步快速上手 →</button></p>

    <div v-if="account.signedIn&&dashboard.error" class="notice notice--danger dashboard-error"><span>{{dashboard.error}}</span><button class="button button--small button--secondary" type="button" @click="loadHome">重试</button></div>
    <AppState v-else-if="account.signedIn&&dashboard.loading&&!dashboard.data" kind="loading" title="正在整理工作台" description="正在汇总事项与今日安排。"/>

    <template v-if="account.signedIn&&!dashboard.loading&&dashboard.data">
      <SectionHeader title="今日任务" :description="`${dashboard.data.date} · 截止与已排程任务`">
        <template #action><RouterLink to="/plan?tab=schedule" class="text-link">查看日程</RouterLink></template>
      </SectionHeader>
      <AppState v-if="!todayTasks.length" title="今天没有待处理任务" description="今日截止与今日已排程的待办都会显示在这里。"/>
      <TaskTimeline v-else :tasks="todayTasks" @change="changeTask"/>
    </template>

    <SectionHeader title="最近事项" :description="account.signedIn?'按最近更新时间排列':'以下内容为演示数据'">
      <template #action><RouterLink to="/cases" class="text-link">查看全部</RouterLink></template>
    </SectionHeader>
    <AppState v-if="!account.signedIn&&cases.loading" kind="loading" title="正在整理事项" description="很快就好，请稍候。"/>
    <div v-else-if="!account.signedIn&&cases.error" class="notice notice--danger">{{cases.error}}</div>
    <AppState v-else-if="!recentCases.length&&!dashboard.loading&&!(account.signedIn&&dashboard.error)" title="还没有事项" description="导入一份通知，知事会帮你整理成清晰的行动步骤。"><RouterLink class="button button--primary" to="/imports/new">导入第一份通知</RouterLink></AppState>
    <div v-else-if="recentCases.length" class="case-list"><CaseCard v-for="item in recentCases" :key="item.id" :item="item"/></div>

    <AppBottomSheet :open="guideOpen" title="快速上手" @close="closeGuide">
      <div class="home-onboarding">
        <p class="home-onboarding__progress" role="status">第 {{guideStep+1}} 步，共 {{guide.length}} 步</p>
        <h2>{{guide[guideStep].title}}</h2><p>{{guide[guideStep].description}}</p>
        <div class="home-onboarding__actions"><button v-if="guideStep>0" class="button button--secondary" type="button" @click="guideStep--">上一步</button><button class="button button--primary" type="button" @click="nextGuide">{{guideStep===guide.length-1?'完成引导':'下一步'}}</button></div>
        <RouterLink class="text-link" to="/guide?from=/home" @click="closeGuide">查看完整使用指南 →</RouterLink>
      </div>
    </AppBottomSheet>
  </div>
</template>

<style scoped>
.home-guide-entry{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin:0 2px 16px;font-size:12px}
.home-guide-entry button{min-height:36px;padding:6px 0;border:0;background:transparent;color:var(--color-primary-strong);font-size:12px;cursor:pointer}
.home-onboarding{padding:8px 0}
.home-onboarding__progress{color:var(--color-primary-strong);font-size:13px}
.home-onboarding h2{margin-top:14px;font-size:23px}
.home-onboarding h2+p{margin-top:10px;font-size:14px;line-height:1.8}
.home-onboarding__actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:10px;margin:24px 0 18px}
.home-onboarding>.text-link{display:block;padding:8px 0;font-size:13px;text-align:center}
</style>
