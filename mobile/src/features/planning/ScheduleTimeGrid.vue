<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue';
import {layoutDays,kindLabels,minuteLabel,type GridItem,type Segment} from './scheduleGrid';
const props=defineProps<{items:GridItem[];days:string[];evidence:Record<string,string>}>();
const emit=defineEmits<{select:[item:GridItem,trigger:HTMLElement];day:[day:string]}>();
const scroller=ref<HTMLElement|null>(null);
const layout=computed(()=>layoutDays(props.items,props.days));
type OverlapGroup={start:number;end:number;segments:Segment[]};
const displayDays=computed(()=>layout.value.days.map(day=>{
 const groups:OverlapGroup[]=[];
 for(const s of day.segments){
  const last=groups[groups.length-1];
  if(last&&s.start<last.end){last.end=Math.max(last.end,s.end);last.segments.push(s)}
  else groups.push({start:s.start,end:s.end,segments:[s]});
 }
 return {...day,groups:props.days.length>1?groups.filter(g=>g.segments.length>1):[],visible:props.days.length>1?groups.filter(g=>g.segments.length===1).flatMap(g=>g.segments):day.segments};
}));
const overlapDialog=ref<HTMLDialogElement|null>(null),activeGroup=ref<OverlapGroup|null>(null);
let overlapTrigger:HTMLElement|null=null;
async function openOverlap(group:OverlapGroup,event:Event){activeGroup.value=group;overlapTrigger=event.currentTarget as HTMLElement;await nextTick();overlapDialog.value?.showModal()}
function closeOverlap(){overlapDialog.value?.close();activeGroup.value=null;overlapTrigger?.focus()}
function chooseOverlap(item:GridItem){const trigger=overlapTrigger;closeOverlap();if(trigger)emit('select',item,trigger)}
watch(()=>[props.days,props.items],()=>closeOverlap());
const shortSlots=computed(()=>layout.value.days.flatMap(day=>day.segments.filter(s=>s.end-s.start<30)));
// Three pixels per minute keeps the continuous hour axis proportional.
const minuteHeight=3;
const columns=computed(()=>`38px repeat(${layout.value.days.length}, minmax(0,1fr))`);
const style=(s:Segment)=>({top:`${s.start*minuteHeight}px`,height:`${(s.end-s.start)*minuteHeight}px`,left:`calc(${s.lane*100/s.lanes}% + 1px)`,width:`calc(${100/s.lanes}% - 2px)`});
function needsReview(item:GridItem){return !item.evidence_ids.length||item.evidence_ids.some(id=>!props.evidence[id])}
function choose(item:GridItem,event:Event){emit('select',item,event.currentTarget as HTMLElement)}
onMounted(()=>{if(scroller.value)scroller.value.scrollTop=480*minuteHeight});
</script>
<template>
 <div :class="['time-grid-shell',{'time-grid-shell--week':days.length>1}]">
  <p v-if="layout.errors.length" class="notice notice--danger" role="alert">{{layout.errors.join('；')}}</p>
  <p v-if="layout.days.every(d=>!d.segments.length)" class="grid-empty" role="status">{{days.length===1?'当天':'本周'}}没有样例安排</p>
  <section v-if="shortSlots.length" class="grid-short-slots" aria-label="短时段完整标题">
   <h3>短时段</h3>
   <p>完整标题在这里查看，点击打开详情。</p>
   <button v-for="s in shortSlots" :key="s.day+s.item.id" type="button" :data-short-item="s.item.id" @click="choose(s.item,$event)">
    <span class="short-slot-time">{{days.length>1?s.day.slice(5)+' · ':''}}{{minuteLabel(s.start)}}–{{minuteLabel(s.end)}} · {{kindLabels[s.item.kind]}}</span>
    <strong>{{s.item.title}}</strong><span v-if="needsReview(s.item)" class="short-slot-status">待核对</span><span v-if="s.conflict" class="short-slot-status">时间重叠</span>
   </button>
  </section>
  <div ref="scroller" class="grid-scroll" tabindex="0" role="region" aria-label="时间网格，可横向和纵向滚动">
   <div class="grid-canvas" :style="{gridTemplateColumns:columns,width:'100%'}">
    <div class="grid-corner">上海<br>时间</div>
    <button v-for="day in days" :key="'header'+day" class="grid-date" type="button" :aria-label="'查看'+day+'日视图'" @click="emit('day',day)"><span>{{['日','一','二','三','四','五','六'][new Date(day+'T00:00:00Z').getUTCDay()]}}</span><small>{{Number(day.slice(8))}}</small></button>
    <div class="grid-ruler"><span v-for="hour in 25" :key="hour" :style="{top:`${(hour-1)*60*minuteHeight}px`}">{{minuteLabel((hour-1)*60)}}</span></div>
    <div v-for="day in displayDays" :key="day.day" class="grid-day" :data-day="day.day">
     <button v-for="s in day.visible" :key="s.item.id" type="button" :class="['grid-block','grid-block--'+s.item.kind,{'grid-block--compact':(s.end-s.start)*minuteHeight<54,'grid-block--tiny':(s.end-s.start)*minuteHeight<16}]" :style="style(s)" :data-item="s.item.id" :aria-label="`${kindLabels[s.item.kind]} ${s.item.title} ${minuteLabel(s.start)}至${minuteLabel(s.end)}${s.conflict?'，时间重叠':''}${needsReview(s.item)?'，待核对':''}`" @click="choose(s.item,$event)"><strong>{{needsReview(s.item)?'待核对 · ':''}}{{s.item.title}}</strong><span>{{kindLabels[s.item.kind]}} · {{minuteLabel(s.start)}}</span><span v-if="s.conflict">时间重叠</span></button>
     <button v-for="g in day.groups" :key="'group'+g.start" type="button" class="grid-block grid-overlap" :data-overlap-count="g.segments.length" :style="{top:`${g.start*minuteHeight}px`,height:`${(g.end-g.start)*minuteHeight}px`}" :aria-label="`${day.day} ${minuteLabel(g.start)}至${minuteLabel(g.end)}，${g.segments.length}项时间重叠，展开安排`" @click="openOverlap(g,$event)"><strong>{{g.segments.length}}项</strong><span>重叠</span><span>点看</span><span v-if="g.segments.some(s=>needsReview(s.item))">待核对</span></button>
    </div>
   </div>
  </div>
  <dialog ref="overlapDialog" class="overlap-dialog" aria-label="重叠时段安排" @cancel.prevent="closeOverlap" @click="($event.target===overlapDialog)&&closeOverlap()">
   <template v-if="activeGroup"><header><h3>{{activeGroup.segments.length}}项安排 · 时间重叠</h3><button type="button" aria-label="关闭重叠安排" @click="closeOverlap">关闭</button></header><p>{{activeGroup.segments[0].day}} · 各项实际时间如下</p>
    <button v-for="s in activeGroup.segments" :key="s.item.id" class="overlap-item" :data-overlap-item="s.item.id" type="button" @click="chooseOverlap(s.item)"><span>{{minuteLabel(s.start)}}–{{minuteLabel(s.end)}} · {{kindLabels[s.item.kind]}}</span><strong>{{s.item.title}}</strong><span v-if="needsReview(s.item)">待核对</span><span>查看详情 ›</span></button>
   </template>
  </dialog>
  <details class="grid-index"><summary>时段索引 · 短时段也可在这里查看详情</summary><section v-for="day in layout.days" :key="day.day"><h3>{{day.day}}</h3><p v-if="!day.segments.length">当天没有样例安排</p><button v-for="s in day.segments" :key="s.item.id" type="button" :data-index-item="s.item.id" @click="choose(s.item,$event)">{{minuteLabel(s.start)}}–{{minuteLabel(s.end)}} · {{kindLabels[s.item.kind]}} · {{s.item.title}}<span v-if="needsReview(s.item)"> · 待核对</span><span v-if="s.conflict"> · 时间重叠</span></button></section></details>
 </div>
</template>
<style scoped>
.time-grid-shell{min-width:0}.grid-empty{padding:12px}.grid-scroll{height:68dvh;min-height:260px;overflow:auto;overscroll-behavior:contain;border:1px solid var(--color-border);border-radius:14px;background:#fff;position:relative}.grid-canvas{display:grid;min-width:100%;width:100%;grid-template-rows:48px 4320px;padding-bottom:16px}.grid-corner,.grid-date{position:sticky;top:0;z-index:3;background:#edf7f5;border:0;border-bottom:1px solid #c9ddda;min-height:44px;font-size:12px}.grid-corner{left:0;z-index:5;text-align:center;padding:4px}.grid-date{cursor:pointer;border-left:1px solid #c9ddda}.grid-date{min-width:0;padding:3px 0}.grid-date span,.grid-date small{display:block}.grid-date small{margin:2px 0 0;font-size:12px}.grid-ruler{position:sticky;left:0;z-index:2;background:#f7faf9;height:4320px;font-size:10px;color:#50665f}.grid-ruler span{position:absolute;right:6px;transform:translateY(-50%)}.grid-ruler span:first-child{transform:none}.grid-day{position:relative;height:4320px;border-left:1px solid #dbe7e4;background:repeating-linear-gradient(to bottom,transparent 0,transparent 89px,#edf2f0 89px,#edf2f0 90px,transparent 90px,transparent 179px,#dbe7e4 179px,#dbe7e4 180px)}.grid-block{position:absolute;box-sizing:border-box;min-height:0;border:1px solid #17836e;border-left-width:2px;border-radius:5px;padding:3px 2px;text-align:left;overflow:hidden;background:#d6f3e8;color:#174b3e;cursor:pointer;font-size:12px;line-height:1.4}.grid-block strong,.grid-block span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.grid-block--course{background:#dfedf8;border-color:#537fa4;color:#234e70}.grid-block--busy{background:#e9edf0;border-color:#76848b;color:#35464e}.grid-block:focus-visible,.grid-date:focus-visible,.grid-index button:focus-visible{outline:3px solid #b46013;outline-offset:-3px}.grid-index{margin-top:12px;padding:12px;border:1px solid var(--color-border);border-radius:12px;background:#fff}.grid-index summary{min-height:44px;cursor:pointer}.grid-index h3{font-size:14px;margin:10px 0}.grid-index button{display:block;width:100%;min-height:44px;padding:8px;text-align:left;white-space:normal;overflow-wrap:anywhere;border:0;border-top:1px solid #dae6e2;background:white;color:#245c50}
.grid-short-slots{margin-bottom:12px;padding:12px;border:1px solid var(--color-border);border-radius:12px;background:#fff}.grid-short-slots h3{margin:0;font-size:14px}.grid-short-slots p{margin:4px 0 8px;font-size:12px;color:#50665f}.grid-short-slots button{display:block;width:100%;min-height:44px;padding:10px 0;border:0;border-top:1px solid #dae6e2;background:transparent;text-align:left;color:#245c50;cursor:pointer}.grid-short-slots strong{display:block;white-space:normal;overflow-wrap:anywhere;line-height:1.5;font-size:14px}.short-slot-time,.short-slot-status{font-size:12px;line-height:1.5}.short-slot-status{display:inline-block;margin-right:8px}.grid-short-slots button:focus-visible{outline:3px solid #b46013;outline-offset:2px}.grid-block--compact{padding:0 3px;line-height:12px}.grid-block--compact span{display:none}.grid-block--tiny strong{display:none}
.grid-block strong{white-space:normal;overflow-wrap:anywhere;word-break:normal}.grid-block--compact{padding:0 2px;line-height:14px}.time-grid-shell--week .grid-block span{font-size:10px}.time-grid-shell--week .grid-block{border-left-width:1px}.grid-ruler span{right:3px}
.grid-overlap{left:1px;width:calc(100% - 2px);background:#e5e9fb;border-color:#6a78ad;color:#344575;text-align:center}.grid-overlap strong{font-size:14px}.grid-overlap span{white-space:normal}.overlap-dialog{position:fixed;inset:auto 0 0;margin:0 auto;box-sizing:border-box;width:min(100%,480px);max-height:80dvh;overflow:auto;padding:18px;border:0;border-radius:20px 20px 0 0;background:#fff;color:#173f34}.overlap-dialog::backdrop{background:#142e2866}.overlap-dialog header{display:flex;align-items:center;justify-content:space-between;gap:10px}.overlap-dialog h3{font-size:17px;margin:0}.overlap-dialog p{font-size:12px;margin:10px 0;color:#50665f}.overlap-dialog button{min-height:44px;border:1px solid #c8dcd4;border-radius:10px;padding:10px;background:#f4f9f7;color:inherit;cursor:pointer}.overlap-dialog .overlap-item{display:block;text-align:left;width:100%;margin:8px 0}.overlap-item strong{display:block;font-size:15px;white-space:normal;overflow-wrap:anywhere;line-height:1.5}.overlap-item span{display:block;font-size:12px}.overlap-dialog button:focus-visible{outline:3px solid #b46013;outline-offset:2px}
</style>
