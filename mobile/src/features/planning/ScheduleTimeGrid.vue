<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {layoutDays,kindLabels,minuteLabel,type GridItem,type Segment} from './scheduleGrid';
const props=defineProps<{items:GridItem[];days:string[];evidence:Record<string,string>}>();
const emit=defineEmits<{select:[item:GridItem,trigger:HTMLElement];day:[day:string]}>();
const scroller=ref<HTMLElement|null>(null);
const layout=computed(()=>layoutDays(props.items,props.days));
const columns=computed(()=>`52px ${layout.value.days.map(d=>`minmax(${d.minWidth}px,1fr)`).join(' ')}`);
const style=(s:Segment)=>({top:`${s.start}px`,height:`${s.end-s.start}px`,left:`calc(${s.lane*100/s.lanes}% + 3px)`,width:`calc(${100/s.lanes}% - 6px)`});
function needsReview(item:GridItem){return !item.evidence_ids.length||item.evidence_ids.some(id=>!props.evidence[id])}
function choose(item:GridItem,event:Event){emit('select',item,event.currentTarget as HTMLElement)}
onMounted(()=>{if(scroller.value)scroller.value.scrollTop=480});
</script>
<template>
 <div class="time-grid-shell">
  <p v-if="layout.errors.length" class="notice notice--danger" role="alert">{{layout.errors.join('；')}}</p>
  <p v-if="layout.days.every(d=>!d.segments.length)" class="grid-empty" role="status">{{days.length===1?'当天':'本周'}}没有样例安排</p>
  <div ref="scroller" class="grid-scroll" tabindex="0" role="region" aria-label="时间网格，可横向和纵向滚动">
   <div class="grid-canvas" :style="{gridTemplateColumns:columns,width:`max(100%, ${52+layout.days.reduce((sum,d)=>sum+d.minWidth,0)}px)`}">
    <div class="grid-corner">上海<br>时间</div>
    <button v-for="day in days" :key="'header'+day" class="grid-date" type="button" :aria-label="'查看'+day+'日视图'" @click="emit('day',day)">{{day.slice(5)}}<small>{{['日','一','二','三','四','五','六'][new Date(day+'T00:00:00Z').getUTCDay()]}}</small></button>
    <div class="grid-ruler"><span v-for="hour in 25" :key="hour" :style="{top:`${(hour-1)*60}px`}">{{minuteLabel((hour-1)*60)}}</span></div>
    <div v-for="day in layout.days" :key="day.day" class="grid-day" :data-day="day.day">
     <button v-for="s in day.segments" :key="s.item.id" type="button" :class="['grid-block','grid-block--'+s.item.kind]" :style="style(s)" :data-item="s.item.id" :aria-label="`${kindLabels[s.item.kind]} ${s.item.title} ${minuteLabel(s.start)}至${minuteLabel(s.end)}${s.conflict?'，时间重叠':''}${needsReview(s.item)?'，待核对':''}`" @click="choose(s.item,$event)"><strong>{{needsReview(s.item)?'待核对 · ':''}}{{s.item.title}}</strong><span>{{kindLabels[s.item.kind]}} · {{minuteLabel(s.start)}}</span><span v-if="s.conflict">时间重叠</span></button>
    </div>
   </div>
  </div>
  <details class="grid-index"><summary>时段索引 · 短时段也可在这里查看详情</summary><section v-for="day in layout.days" :key="day.day"><h3>{{day.day}}</h3><p v-if="!day.segments.length">当天没有样例安排</p><button v-for="s in day.segments" :key="s.item.id" type="button" :data-index-item="s.item.id" @click="choose(s.item,$event)">{{minuteLabel(s.start)}}–{{minuteLabel(s.end)}} · {{kindLabels[s.item.kind]}} · {{s.item.title}}<span v-if="needsReview(s.item)"> · 待核对</span><span v-if="s.conflict"> · 时间重叠</span></button></section></details>
 </div>
</template>
<style scoped>
.time-grid-shell{min-width:0}.grid-empty{padding:12px}.grid-scroll{height:60vh;min-height:220px;overflow:auto;overscroll-behavior:contain;border:1px solid var(--color-border);border-radius:14px;background:#fff;position:relative}.grid-canvas{display:grid;min-width:100%;width:100%;grid-template-rows:44px 1440px;padding-bottom:16px}.grid-corner,.grid-date{position:sticky;top:0;z-index:3;background:#edf7f5;border:0;border-bottom:1px solid #c9ddda;min-height:44px;font-size:12px}.grid-corner{left:0;z-index:5;text-align:center;padding:4px}.grid-date{cursor:pointer;border-left:1px solid #c9ddda}.grid-date small{margin-left:6px}.grid-ruler{position:sticky;left:0;z-index:2;background:#f7faf9;height:1440px;font-size:10px;color:#50665f}.grid-ruler span{position:absolute;right:6px;transform:translateY(-50%)}.grid-ruler span:first-child{transform:none}.grid-day{position:relative;height:1440px;border-left:1px solid #dbe7e4;background:repeating-linear-gradient(to bottom,transparent 0,transparent 29px,#edf2f0 29px,#edf2f0 30px,transparent 30px,transparent 59px,#dbe7e4 59px,#dbe7e4 60px)}.grid-block{position:absolute;box-sizing:border-box;min-height:0;border:1px solid #17836e;border-left-width:3px;border-radius:5px;padding:2px 3px;text-align:left;overflow:hidden;background:#d6f3e8;color:#174b3e;cursor:pointer;font-size:11px;line-height:1.35}.grid-block strong,.grid-block span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.grid-block--course{background:#dfedf8;border-color:#537fa4;color:#234e70}.grid-block--busy{background:#e9edf0;border-color:#76848b;color:#35464e}.grid-block:focus-visible,.grid-date:focus-visible,.grid-index button:focus-visible{outline:3px solid #b46013;outline-offset:-3px}.grid-index{margin-top:12px;padding:12px;border:1px solid var(--color-border);border-radius:12px;background:#fff}.grid-index summary{min-height:44px;cursor:pointer}.grid-index h3{font-size:14px;margin:10px 0}.grid-index button{display:block;width:100%;min-height:44px;padding:8px;text-align:left;white-space:normal;overflow-wrap:anywhere;border:0;border-top:1px solid #dae6e2;background:white;color:#245c50}
</style>
