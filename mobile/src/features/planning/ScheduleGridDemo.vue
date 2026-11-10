<script setup lang="ts">
import {computed,nextTick,ref} from 'vue';
import ScheduleTimeGrid from './ScheduleTimeGrid.vue';
import {addDays,weekStart,displayInstant,dayKey,kindLabels,type GridItem} from './scheduleGrid';
import {anchorDay,gridFixtures,exceptionalFixtures,fixtureCourses,fixtureEvidence} from './scheduleGridFixtures';
const mode=ref<'day'|'week'>('day'),selected=ref(anchorDay),exceptional=ref(false);
const days=computed(()=>mode.value==='day'?[selected.value]:Array.from({length:7},(_,i)=>addDays(weekStart(selected.value),i)));
const items=computed(()=>exceptional.value?exceptionalFixtures:gridFixtures);
const detail=ref<GridItem|null>(null),dialog=ref<HTMLDialogElement|null>(null);
let trigger:HTMLElement|null=null;
async function show(item:GridItem,element:HTMLElement){trigger=element;detail.value=item;await nextTick();dialog.value?.showModal()}
function close(){dialog.value?.close();detail.value=null;trigger?.focus()}
function navigate(n:number){selected.value=addDays(selected.value,n*(mode.value==='day'?1:7))}
function changeDay(day:string){selected.value=day;mode.value='day'}
const references=computed(()=>detail.value?.evidence_ids.map(id=>fixtureEvidence[id]).filter(Boolean)||[]);
</script>
<template>
 <section class="grid-demo" aria-label="固定样例时间网格">
  <div class="demo-banner"><strong>固定样例 · 不保存到账户</strong><p>上海时间 · 2026年11月9日样例周。仅查看，不生成或提交排程。</p></div>
  <div class="demo-controls"><div class="view-switch" role="group" aria-label="时间网格视图"><button type="button" :aria-pressed="mode==='day'" @click="mode='day'">日视图</button><button type="button" :aria-pressed="mode==='week'" @click="mode='week'">周视图</button></div><button type="button" @click="selected=anchorDay">回到样例周</button></div>
  <div class="date-nav"><button type="button" :aria-label="mode==='day'?'前一天':'前一周'" @click="navigate(-1)">‹</button><h2 aria-live="polite">{{days[0]}}{{mode==='week'?' — '+days[6]:''}}</h2><button type="button" :aria-label="mode==='day'?'后一天':'后一周'" @click="navigate(1)">›</button></div>
  <label class="date-picker">查看日期 <input type="date" :value="selected" @change="($event.target as HTMLInputElement).value && (selected=($event.target as HTMLInputElement).value)"></label>
  <p class="demo-legend">课程 · 任务 · 忙碌 <span>重叠时段分列显示；周视图可左右滑动</span></p>
  <ScheduleTimeGrid :items="items" :days="days" :evidence="fixtureEvidence" @select="show" @day="changeDay"/>
  <label class="exception-toggle"><input v-model="exceptional" type="checkbox">查看异常样例（非法时间与缺少依据）</label>
  <dialog ref="dialog" class="grid-detail" aria-label="样例时段详情" @cancel.prevent="close" @click="($event.target===dialog)&&close()">
   <template v-if="detail"><header><h2>样例时段详情</h2><button type="button" aria-label="关闭样例详情" @click="close">关闭</button></header><h3>{{detail.title}}</h3><p>{{kindLabels[detail.kind]}} · 只读固定样例</p><p>{{displayInstant(detail.starts_at)}} — {{displayInstant(detail.ends_at)}}</p><p v-if="dayKey(detail.starts_at)!==dayKey(detail.ends_at)">跨日时段，网格按午夜拆分显示，仍为同一条样例。</p><p v-if="detail.courseId">{{fixtureCourses[detail.courseId]||'课程详情待核对'}}</p><h3>样例输入依据</h3><p v-if="!references.length||references.length!==detail.evidence_ids.length">待核对：样例依据缺失或无效。</p><p v-for="(text,i) in references" :key="i">{{text}}</p></template>
  </dialog>
 </section>
</template>
<style scoped>
.grid-demo{min-width:0;max-width:100%}.demo-banner{background:#e5f5ee;border:1px solid #b8dccc;padding:14px;border-radius:16px;margin:12px 0}.demo-banner p,.demo-legend{font-size:12px;margin-top:5px;color:#4a665d}.demo-controls,.date-nav{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:10px 0}.demo-controls button,.date-nav button{min-height:44px;min-width:44px;padding:8px 10px;border:1px solid #c8dcd4;border-radius:10px;background:white;color:#24594b;cursor:pointer}.view-switch{display:flex;gap:4px}.view-switch button[aria-pressed=true]{background:#087f69;color:#fff}.date-nav h2{font-size:14px;text-align:center;overflow-wrap:anywhere}.date-picker{white-space:nowrap;display:flex;align-items:center;gap:10px;margin:10px 0}.date-picker input{min-width:0;flex:1;width:auto;min-height:44px;max-width:100%;padding:6px;border:1px solid #c8dcd4;border-radius:8px}.demo-legend{margin-bottom:10px}.demo-legend span{display:block}.exception-toggle{display:flex;align-items:center;gap:8px;min-height:44px;margin:14px 0}.grid-detail{position:fixed;inset: auto 0 0;margin:0 auto;width:min(100%,600px);max-height:80vh;overflow:auto;border:0;border-radius:20px 20px 0 0;padding:20px;color:#173f34;background:#fff}.grid-detail::backdrop{background:#142e2866}.grid-detail header{display:flex;justify-content:space-between;align-items:center;gap:12px}.grid-detail h2{font-size:18px}.grid-detail h3{margin-top:16px}.grid-detail p{margin-top:12px;overflow-wrap:anywhere}.grid-detail button{min-width:44px;min-height:44px;border:1px solid #b8dccc;border-radius:10px;background:#edf8f3}
</style>
