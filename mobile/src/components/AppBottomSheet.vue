<script setup lang="ts">
import {nextTick,onBeforeUnmount,ref,watch} from 'vue';
const props=defineProps<{open:boolean;title:string}>();
const emit=defineEmits<{close:[]}>();
const panel=ref<HTMLElement|null>(null);
let oldOverflow='';
watch(()=>props.open,async value=>{
  if(value){oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden';await nextTick();panel.value?.focus()}
  else document.body.style.overflow=oldOverflow;
},{immediate:true});
onBeforeUnmount(()=>{document.body.style.overflow=oldOverflow});
function keydown(event:KeyboardEvent){if(event.key==='Escape')emit('close')}
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet-fade">
      <div v-if="open" class="app-sheet-backdrop" @click.self="$emit('close')" @keydown="keydown">
        <section ref="panel" class="app-sheet" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1">
          <div class="app-sheet__handle" aria-hidden="true"></div>
          <header class="app-sheet__header"><h2>{{title}}</h2><button class="icon-button icon-button--plain" type="button" :aria-label="`关闭${title}`" @click="$emit('close')">×</button></header>
          <div class="app-sheet__body"><slot/></div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
