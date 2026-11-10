<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {useAccountStore} from '../../stores/account';
import {useCasesStore} from '../cases/store';
import AppHeader from '../../components/AppHeader.vue';
import GuideLink from '../../components/GuideLink.vue';
import AppState from '../../components/AppState.vue';
import StatusBadge from '../../components/StatusBadge.vue';
import TaskTimeline from '../../components/TaskTimeline.vue';
import AppBottomSheet from '../../components/AppBottomSheet.vue';
import PlanSchedule from './PlanSchedule.vue';
import ScheduleGridDemo from './ScheduleGridDemo.vue';
const gridDemo=ref(false);

const route=useRoute(),router=useRouter(),account=useAccountStore(),cases=useCasesStore();
const selectedId=ref(''),planLoading=ref(false),pageError=ref(''),pickerOpen=ref(false);
const activeTab=computed<'steps'|'schedule'>(()=>route.query.tab==='schedule'?'schedule':'steps');
onMounted(async()=>{await cases.load();if(cases.items.length){const requested=String(route.query.case||'');const first=cases.items.some(item=>item.id===requested)?requested:cases.items[0].id;await selectCase(first)}});
watch(()=>route.query.case,async value=>{const id=String(value||'');if(id&&id!==selectedId.value&&cases.items.some(item=>item.id===id))await selectCase(id)});
async function selectCase(id:string){selectedId.value=id;planLoading.value=true;pageError.value='';try{await cases.loadOne(id);await cases.loadResources(id);await cases.loadPlan(id)}catch(e:any){pageError.value=e?.message||'执行计划读取失败'}finally{planLoading.value=false}}
async function chooseCase(id:string){pickerOpen.value=false;if(id!==selectedId.value)await selectCase(id);await router.replace({path:'/plan',query:{...route.query,case:id}})}
async function switchTab(tab:'steps'|'schedule'){await router.replace({path:'/plan',query:{...route.query,tab,...(selectedId.value?{case:selectedId.value}:{})}})}
async function changeStatus(id:string,status:string){try{await cases.setTask(id,status)}catch(e:any){pageError.value=e?.message||'状态更新失败'}}
</script>

<template>
  <div class="page page--plan">
    <AppHeader title="执行计划"/>
    <GuideLink topic="plan" label="任务状态、课表避让和排程确认怎么用？"/>
    <button v-if="!gridDemo" class="button button--secondary" type="button" @click="gridDemo=true">查看时间网格样例</button>
    <template v-if="gridDemo"><button class="button button--secondary" type="button" @click="gridDemo=false">返回日程</button><ScheduleGridDemo/></template>
    <template v-else>
    <AppState v-if="cases.loading&&!cases.items.length" kind="loading" title="正在生成计划视图"/>
    <AppState v-else-if="!cases.items.length" title="还没有可执行事项" description="完成一次通知导入后，证据充分的步骤会出现在这里。"><RouterLink class="button button--primary" to="/imports/new">导入通知</RouterLink></AppState>
    <template v-else>
      <button v-if="cases.selected" class="plan-case-card" type="button" aria-haspopup="dialog" @click="pickerOpen=true">
        <span class="plan-case-card__copy"><span class="text-label">当前查看事项</span><strong>{{cases.selected.title}}</strong><span class="plan-case-card__meta"><StatusBadge :value="cases.selected.relevance"/><span>{{cases.selected.deadline?'截止 '+cases.selected.deadline:'截止时间待核对'}}</span></span></span><img src="/assets/icons/status/icon_chevron.svg" alt="" aria-hidden="true">
      </button>
      <div class="plan-primary-tabs" role="tablist" aria-label="执行计划视图"><button :class="{active:activeTab==='steps'}" type="button" role="tab" :aria-selected="activeTab==='steps'" @click="switchTab('steps')">行动步骤</button><button :class="{active:activeTab==='schedule'}" type="button" role="tab" :aria-selected="activeTab==='schedule'" @click="switchTab('schedule')">日程安排</button></div>
      <div v-if="!account.signedIn" class="mode-banner mode-banner--compact"><span class="mode-banner__dot"></span><div><b>离线样例计划</b><p>任务状态保存在当前浏览器；账户计划登录后由服务端持久化。</p></div></div>
      <div v-if="pageError" class="notice notice--danger">{{pageError}}</div>
      <AppState v-if="planLoading" kind="loading" title="正在整理执行顺序"/>
      <template v-else-if="activeTab==='steps'">
        <section v-if="cases.plan" class="plan-summary"><div><span class="text-label">总体进度</span><strong>{{cases.plan.overall_progress||0}}%</strong></div><div><span class="text-label">已完成</span><strong>{{cases.plan.completed_tasks||0}}</strong></div><div><span class="text-label">待处理</span><strong>{{cases.plan.pending_tasks||0}}</strong></div></section>
        <div v-if="cases.plan?.current_tasks?.length" class="current-task-strip"><span class="text-label">现在可以做</span><b>{{cases.plan.current_tasks.map((task:any)=>task.title).join('、')}}</b></div>
        <div class="timeline-heading"><h2>行动步骤</h2><span v-if="cases.plan?.ordered_tasks?.length" class="task-count">{{cases.plan.ordered_tasks.length}} 个步骤</span></div>
        <AppState v-if="!cases.plan?.ordered_tasks?.length" title="尚未生成可执行步骤" description="请先在解析结果页核对并确认行动候选；没有原文动作时不会补造任务。"><RouterLink class="button button--primary" :to="`/cases/${selectedId}/analysis`">核对分析候选</RouterLink></AppState>
        <TaskTimeline v-else :tasks="cases.plan.ordered_tasks" @change="changeStatus"/>
        <div class="plan-encouragement"><div><span class="text-label">稳稳向前</span><h3>每完成一步，都离目标更近。</h3><p>当前步骤、预计耗时和材料均以服务端返回的任务计划为准。</p></div><img src="/assets/illustrations/hero_goal_mountain.png" alt="" aria-hidden="true"></div>
      </template>
      <PlanSchedule v-else :case-id="selectedId" :tasks="cases.plan?.ordered_tasks||[]"/>
    </template>
    </template>
    <AppBottomSheet :open="pickerOpen" title="选择查看事项" @close="pickerOpen=false"><div class="case-sheet__list"><button v-for="item in cases.items" :key="item.id" :class="['case-sheet__item',{active:item.id===selectedId}]" type="button" @click="chooseCase(item.id)"><span><strong>{{item.title}}</strong><small>{{item.deadline?'截止 '+item.deadline:'截止时间待核对'}}</small></span><span class="case-sheet__check">{{item.id===selectedId?'✓':'›'}}</span></button></div></AppBottomSheet>
  </div>
</template>
