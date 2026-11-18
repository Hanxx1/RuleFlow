<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue';
import {api} from '../../core/http';
import ScheduleTimeGrid from './ScheduleTimeGrid.vue';
import {addDays,weekStart,displayInstant,dayKey,kindLabels,type GridItem} from './scheduleGrid';
import {anchorDay,gridFixtures,exceptionalFixtures,fixtureCourses,fixtureEvidence} from './scheduleGridFixtures';
const props=defineProps<{source:'sample'|'account'}>();
const sample=props.source==='sample';
function homeDay(){return sample?anchorDay:dayKey(new Date().toISOString())}
const mode=ref<'day'|'week'>('day'),selected=ref(homeDay()),exceptional=ref(false);
const days=computed(()=>mode.value==='day'?[selected.value]:Array.from({length:7},(_,i)=>addDays(weekStart(selected.value),i)));
const accountItems=ref<GridItem[]>([]);
const loading=ref(false),error=ref(''),retry=ref(0);
const firstDay=computed(()=>weekStart(selected.value));
if(!sample){
 watch([firstDay,retry],async ([start],_,onCleanup)=>{
  const request=new AbortController();
  onCleanup(()=>request.abort());
  accountItems.value=[];
  loading.value=true;
  error.value='';
  try{
   const range=new URLSearchParams({from:start+'T00:00:00+08:00',to:addDays(start,7)+'T00:00:00+08:00'});
   const rows:GridItem[]=await api('/api/v1/schedule?'+range,{signal:request.signal});
   if(!request.signal.aborted)accountItems.value=rows.map(row=>({...row,evidence_ids:row.evidence_ids??[]}));
  }catch(e){
   if(!request.signal.aborted)error.value=e instanceof Error?e.message:'日程读取失败';
  }finally{
   if(!request.signal.aborted)loading.value=false;
  }
 },{immediate:true});
}
const evidence:Record<string,string>=sample?fixtureEvidence:{};
const items=computed(()=>sample?(exceptional.value?exceptionalFixtures:gridFixtures):accountItems.value);
const detailTitle=sample?'样例时段详情':'账户日程详情';
const detail=ref<GridItem|null>(null),dialog=ref<HTMLDialogElement|null>(null);
let trigger:HTMLElement|null=null;
async function show(item:GridItem,element:HTMLElement){trigger=element;detail.value=item;await nextTick();dialog.value?.showModal()}
function close(){dialog.value?.close();detail.value=null;trigger?.focus()}
function navigate(n:number){selected.value=addDays(selected.value,n*(mode.value==='day'?1:7))}
function changeDay(day:string){selected.value=day;mode.value='day'}
const references=computed(()=>detail.value?.evidence_ids.map(id=>evidence[id]).filter(Boolean)||[]);
</script>
<template>
 <section class="grid-demo" :aria-label="sample?'固定样例时间网格':'账户日程网格'">
  <h2 v-if="!sample">账户日程网格</h2>
  <div v-else class="demo-banner"><strong>固定样例 · 不保存到账户</strong><p>上海时间 · 2026年11月9日样例周。仅查看，不生成或提交排程。</p></div>
  <div class="demo-controls"><div class="view-switch" role="group" aria-label="时间网格视图"><button type="button" :aria-pressed="mode==='day'" @click="mode='day'">日视图</button><button type="button" :aria-pressed="mode==='week'" @click="mode='week'">周视图</button></div><button type="button" @click="selected=homeDay()">{{sample?'回到样例周':'今天'}}</button></div>
  <div class="date-nav"><button type="button" :aria-label="mode==='day'?'前一天':'前一周'" @click="navigate(-1)">‹</button><h2 aria-live="polite">{{days[0]}}{{mode==='week'?' — '+days[6]:''}}</h2><button type="button" :aria-label="mode==='day'?'后一天':'后一周'" @click="navigate(1)">›</button></div>
  <label class="date-picker">查看日期 <input type="date" :value="selected" @change="($event.target as HTMLInputElement).value && (selected=($event.target as HTMLInputElement).value)"></label>
  <p class="demo-legend">课程 · 任务 · 忙碌 <span>七天同屏，上下滑动查看时间；点击重叠卡片展开全部安排</span></p>
  <p v-if="error" role="alert">{{error}} <button type="button" @click="retry++">重试</button></p>
  <p v-else-if="loading" role="status">正在读取账户日程</p>
  <ScheduleTimeGrid v-else :sample="sample" :items="items" :days="days" :evidence="evidence" @select="show" @day="changeDay"/>
  <label v-if="sample" class="exception-toggle"><input v-model="exceptional" type="checkbox">查看异常样例（非法时间与缺少依据）</label>
  <dialog ref="dialog" class="grid-detail" :aria-label="detailTitle" @cancel.prevent="close" @click="($event.target===dialog)&&close()">
   <template v-if="detail"><header><h2>{{detailTitle}}</h2><button type="button" :aria-label="sample?'关闭样例详情':'关闭日程详情'" @click="close">关闭</button></header><h3>{{detail.title}}</h3><p>{{kindLabels[detail.kind]}} · {{sample?'只读固定样例':'账户日程'}}</p><p>{{displayInstant(detail.starts_at)}} — {{displayInstant(detail.ends_at)}}</p><p v-if="dayKey(detail.starts_at)!==dayKey(detail.ends_at)">跨日时段，网格按午夜拆分显示，仍为同一条安排。</p><p v-if="sample && detail.courseId">{{fixtureCourses[detail.courseId]||'课程详情待核对'}}</p><h3>{{sample?'样例输入依据':'日程依据'}}</h3><p v-if="!references.length||references.length!==detail.evidence_ids.length">待核对：{{sample?'样例':'日程'}}依据缺失或无效。</p><p v-for="(text,i) in references" :key="i">{{text}}</p></template>
  </dialog>
 </section>
</template>
<style scoped>
.grid-demo{min-width:0;max-width:100%}.demo-banner{background:#e5f5ee;border:1px solid #b8dccc;padding:14px;border-radius:16px;margin:12px 0}.demo-banner p,.demo-legend{font-size:12px;margin-top:5px;color:#4a665d}.demo-controls,.date-nav{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:10px 0}.demo-controls button,.date-nav button{min-height:44px;min-width:44px;padding:8px 10px;border:1px solid #c8dcd4;border-radius:10px;background:white;color:#24594b;cursor:pointer}.view-switch{display:flex;gap:4px}.view-switch button[aria-pressed=true]{background:#087f69;color:#fff}.date-nav h2{font-size:14px;text-align:center;overflow-wrap:anywhere}.date-picker{white-space:nowrap;display:flex;align-items:center;gap:10px;margin:10px 0}.date-picker input{min-width:0;flex:1;width:auto;min-height:44px;max-width:100%;padding:6px;border:1px solid #c8dcd4;border-radius:8px}.demo-legend{margin-bottom:10px}.demo-legend span{display:block}.exception-toggle{display:flex;align-items:center;gap:8px;min-height:44px;margin:14px 0}.grid-detail{position:fixed;inset: auto 0 0;margin:0 auto;width:min(100%,600px);max-height:80vh;overflow:auto;border:0;border-radius:20px 20px 0 0;padding:20px;color:#173f34;background:#fff}.grid-detail::backdrop{background:#142e2866}.grid-detail header{display:flex;justify-content:space-between;align-items:center;gap:12px}.grid-detail h2{font-size:18px}.grid-detail h3{margin-top:16px}.grid-detail p{margin-top:12px;overflow-wrap:anywhere}.grid-detail button{min-width:44px;min-height:44px;border:1px solid #b8dccc;border-radius:10px;background:#edf8f3}
</style>
