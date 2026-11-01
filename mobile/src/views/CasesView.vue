<script setup lang="ts">
import {onMounted,ref,watch} from 'vue';
import {useRoute} from 'vue-router';
import {useAccountStore} from '../stores/account';
import {useCasesStore} from '../features/cases/store';
import AppHeader from '../components/AppHeader.vue';
import AppState from '../components/AppState.vue';
import CaseCard from '../components/CaseCard.vue';

const account=useAccountStore(),cases=useCasesStore(),route=useRoute();
const statusFilters=['all','in_progress','due_soon','completed'];
const q=ref(''),status=ref(statusFilters.includes(String(route.query.status))?String(route.query.status):'all'),category=ref(''),sort=ref('updated_at_desc'),searchOpen=ref(false);
onMounted(load);
watch(()=>route.query.status,async value=>{const next=statusFilters.includes(String(value))?String(value):'all';if(next!==status.value){status.value=next;await load()}});
function iso(day:Date){return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`}
async function load(){
  const filters:Record<string,string|number>={q:q.value.trim(),category:category.value,sort:sort.value,limit:100};
  if(status.value==='in_progress'||status.value==='completed')filters.status=status.value;
  if(status.value==='due_soon'){const today=new Date(),end=new Date(today);end.setDate(end.getDate()+7);filters.deadline_from=iso(today);filters.deadline_to=iso(end)}
  await cases.load(filters);
}
async function chooseStatus(value:string){status.value=value;await load()}
</script>

<template>
  <div class="page page--cases">
    <AppHeader title="我的事项">
      <template #action><div class="header-actions"><button class="icon-button" type="button" aria-label="搜索事项" :aria-expanded="searchOpen" @click="searchOpen=!searchOpen"><img src="/assets/icons/actions/icon_search.svg" alt=""></button><RouterLink class="icon-button icon-button--primary" to="/cases/new" aria-label="新建事项"><img src="/assets/icons/actions/icon_add.svg" alt=""></RouterLink></div></template>
    </AppHeader>

    <form v-if="searchOpen" class="case-query" @submit.prevent="load"><input v-model="q" type="search" placeholder="搜索事项标题" aria-label="搜索事项标题"><button class="button button--small button--primary">搜索</button></form>
    <div class="filter-tabs" role="tablist" aria-label="事项筛选">
      <button :class="{active:status==='all'}" role="tab" :aria-selected="status==='all'" @click="chooseStatus('all')">全部</button>
      <button :class="{active:status==='in_progress'}" role="tab" :aria-selected="status==='in_progress'" @click="chooseStatus('in_progress')">进行中</button>
      <button :class="{active:status==='due_soon'}" role="tab" :aria-selected="status==='due_soon'" @click="chooseStatus('due_soon')">即将截止</button>
      <button :class="{active:status==='completed'}" role="tab" :aria-selected="status==='completed'" @click="chooseStatus('completed')">已完成</button>
    </div>
    <div class="case-filter-controls"><label>分类<select v-model="category" @change="load"><option value="">全部分类</option><option value="academic">教务</option><option value="award">奖助评优</option><option value="exam">考试</option><option value="competition">竞赛</option><option value="career">就业实习</option><option value="research">科研申报</option><option value="other">其他</option></select></label><label>排序<select v-model="sort" @change="load"><option value="updated_at_desc">最近更新</option><option value="deadline_asc">截止时间</option><option value="title_asc">标题 A–Z</option></select></label></div>

    <div v-if="!account.signedIn" class="mode-banner mode-banner--compact"><span class="mode-banner__dot"></span><div><b>离线样例</b><p>登录后可搜索、筛选和编辑账户事项。</p></div></div>
    <AppState v-if="cases.loading" kind="loading" title="正在读取事项"/>
    <div v-else-if="cases.error" class="notice notice--danger">{{cases.error}}</div>
    <AppState v-else-if="!cases.items.length" title="没有符合条件的事项" description="调整搜索或筛选条件，也可以导入一份新通知。"><div class="state-actions"><button class="button button--secondary" type="button" @click="q='';category='';status='all';load()">清除筛选</button><RouterLink class="button button--primary" to="/imports/new">导入通知</RouterLink></div></AppState>
    <div v-else class="case-list"><CaseCard v-for="item in cases.items" :key="item.id" :item="item"/></div>
    <RouterLink class="floating-action" to="/imports/new"><span>＋</span>导入通知</RouterLink>
  </div>
</template>
