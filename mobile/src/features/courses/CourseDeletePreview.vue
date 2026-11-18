<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue';
import type {CoursePreview} from './courseModel';

// Read-only local inspection. No inferred Task, timetable or Document relationships.
const props=defineProps<{course:CoursePreview;owner:string;revision:number;unavailable:boolean;sample:boolean}>();
const opened=ref(false),trigger=ref<HTMLButtonElement|null>(null),heading=ref<HTMLHeadingElement|null>(null);
const requirementHistory=computed(()=>props.course.requirements.reduce((count,item)=>count+item.history.length,0));
const recordedSources=computed(()=>props.course.requirements.filter(item=>item.source.trim()).length);
watch(()=>[props.course,props.owner,props.revision,props.unavailable],()=>{opened.value=false},{deep:true,flush:'sync'});
async function open(){if(props.unavailable)return;opened.value=true;await nextTick();heading.value?.focus()}
async function close(){opened.value=false;await nextTick();trigger.value?.focus()}
</script>

<template>
  <section class="delete-preview panel" aria-label="课程删除影响预览" @keydown.esc.stop.prevent="close">
    <button ref="trigger" type="button" class="button button--secondary" :disabled="unavailable" :aria-expanded="opened" @click="opened?close():open()">{{opened?'收起删除影响预览':'预览删除影响'}}</button>
    <p v-if="unavailable" role="status">课程资料可能已变化，请读取最新记录后再预览。</p>
    <template v-if="opened">
      <h2 ref="heading" tabindex="-1">删除前需要核对什么</h2>
      <p class="identity">{{course.term}} · {{course.name}}</p>
      <p>本页只展示影响，不会删除、解绑或取消任何记录。实际删除尚未开放。</p>
      <p v-if="sample">当前为合成样例，仅核对本页内存记录。</p>
      <h3>当前课程的本机记录</h3>
      <p>以下数量来自当前已读取的课程记录；若后续确认删除档案，需要同时核对这些内容。</p>
      <ul>
        <li>课程档案 1 份，包含名称、学期、教师、地点及小组说明；档案旧值 {{course.profileHistory.length}} 条。</li>
        <li>课程要求 {{course.requirements.length}} 项，其中 {{recordedSources}} 项记录了依据文字；要求旧值 {{requirementHistory}} 条。</li>
      </ul>
      <p>依据文字属于用户记录，教师原文尚待核对；旧值历史不能代替备份。可先返回个人画像导出本机备份，备份不包含服务端文件原件。</p>
      <details v-if="course.requirements.length"><summary>核对要求范围与历史数量</summary><ul><li v-for="item in course.requirements" :key="item.id">{{item.label}} · {{item.state}} · 旧值 {{item.history.length}} 条</li></ul></details>
      <h3>关联影响：待核对</h3>
      <p>尚未查询以下关联，不能据此判断没有任务、安排或资料，也不能确定删除后的处理结果。</p>
      <ul class="pending">
        <li><strong>任务：</strong>待核对课程关联的已有任务及保留／解绑方式。</li>
        <li><strong>上课规则与日程：</strong>待核对一课多时段、既有安排及占用变化。</li>
        <li><strong>提醒与排程草案：</strong>待核对取消、失效及恢复范围；本页不会释放任何时段。</li>
        <li><strong>知识资料与来源：</strong>待核对共享资料及其他课程引用；不能因删除一门课程而默认删除共享原件。</li>
      </ul>
      <p>当前范围仅为上方选中的课程档案。同名、跨学期课程不会按名称合并；其他课程与外部引用的影响仍须另行核验。</p>
      <button type="button" class="button button--secondary" @click="close">关闭预览，保留全部数据</button>
    </template>
  </section>
</template>

<style scoped>
.delete-preview{margin:16px 0;overflow-wrap:anywhere}.delete-preview p,.delete-preview li{line-height:1.7}.delete-preview h2{font-size:18px;margin-top:18px}.delete-preview h3{font-size:15px;margin-top:18px}.delete-preview ul{padding-left:22px}.delete-preview li{padding:6px 0}.identity{font-weight:600;white-space:pre-wrap}.pending{background:#f2f6f3;border-radius:10px;padding:10px 14px 10px 30px!important}.delete-preview summary{cursor:pointer;padding:10px 0}.delete-preview button{white-space:normal}.delete-preview :focus-visible{outline:3px solid #208c76;outline-offset:3px}.delete-preview h2:focus{outline:2px solid #208c76;outline-offset:4px}
</style>
