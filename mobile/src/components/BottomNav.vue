<script setup lang="ts">
import {computed} from 'vue';
import {RouterLink,useRoute} from 'vue-router';

const route=useRoute();
const items=[
  {to:'/home',label:'工作台',icon:'nav_home.svg',active:'nav_home_active.svg',matches:['/home']},
  {to:'/cases',label:'我的事项',icon:'nav_tasks.svg',active:'nav_tasks_active.svg',matches:['/cases']},
  {to:'/plan',label:'执行计划',icon:'nav_plan.svg',active:'nav_plan_active.svg',matches:['/plan']},
  {to:'/me',label:'我的',icon:'nav_profile.svg',active:'nav_profile_active.svg',matches:['/me','/profile','/vault','/settings','/help','/about','/guide']},
];
const current=computed(()=>route.path);
function isActive(item:typeof items[number]){return item.matches.some(path=>current.value===path||current.value.startsWith(path+'/'))}
function asset(name:string){return `/assets/icons/navigation/${name}`}
</script>

<template>
  <nav class="bottom-nav" aria-label="主导航">
    <RouterLink v-for="item in items" :key="item.to" :to="item.to" :class="['bottom-nav__item',{active:isActive(item)}]">
      <span class="bottom-nav__icon-wrap"><img :src="asset(isActive(item)?item.active:item.icon)" alt="" aria-hidden="true"></span>
      <span>{{item.label}}</span>
    </RouterLink>
  </nav>
</template>
