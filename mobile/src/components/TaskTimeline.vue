<script setup lang="ts">
import TaskTimelineItem from './TaskTimelineItem.vue';
defineProps<{tasks:any[]}>();
defineEmits<{change:[id:string,status:string]}>();
</script>

<template><div class="task-timeline"><TaskTimelineItem v-for="(task,index) in tasks" :key="task.id" :task="task" :index="index" :last="index===tasks.length-1" @change="(id,status)=>$emit('change',id,status)"/></div></template>
