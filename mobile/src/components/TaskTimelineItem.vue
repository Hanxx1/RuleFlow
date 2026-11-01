<script setup lang="ts">
import StatusBadge from './StatusBadge.vue';
defineProps<{task:any;index:number;last:boolean}>();
const emit=defineEmits<{change:[id:string,status:string]}>();
function choose(event:Event,id:string,status:string){emit('change',id,status);(event.currentTarget as HTMLElement).closest('details')?.removeAttribute('open')}
</script>

<template>
  <article :class="['timeline-item',`timeline-item--${task.status||'todo'}`]">
    <div class="timeline-item__rail"><span class="timeline-item__node">{{task.status==='done'?'✓':index+1}}</span><span v-if="!last" class="timeline-item__line"></span></div>
    <div class="timeline-item__card">
      <div class="timeline-item__heading">
        <details class="task-status-menu"><summary aria-label="修改任务状态"><StatusBadge :value="task.status"/><span aria-hidden="true">⌄</span></summary><div class="task-status-menu__options"><button type="button" @click="choose($event,task.id,'todo')">待完成</button><button type="button" @click="choose($event,task.id,'in_progress')">进行中</button><button type="button" @click="choose($event,task.id,'done')">已完成</button><button type="button" @click="choose($event,task.id,'skipped')">已跳过</button></div></details>
        <span v-if="task.display_time||task.deadline" class="timeline-item__date">{{task.display_time||task.deadline}}</span>
      </div>
      <h3>{{task.title}}</h3><p v-if="task.description">{{task.description}}</p>
      <div class="task-detail-chips"><span v-if="task.duration_minutes">约 {{task.duration_minutes}} 分钟</span><span v-if="!task.is_actionable&&['todo','in_progress'].includes(task.status)">等待前置步骤</span><span v-else-if="task.is_actionable">当前可执行</span></div>
      <div v-if="task.materials?.length" class="task-linked-items"><b>所需材料</b><span v-for="item in task.materials" :key="item.id">{{item.title}}</span></div>
      <div v-if="task.files?.length" class="task-linked-items"><b>相关文件</b><span v-for="item in task.files" :key="item.id">{{item.name}}</span></div>
    </div>
  </article>
</template>
