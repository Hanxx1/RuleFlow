<script setup lang="ts">
import {computed,ref} from 'vue'
import {canWriteMapping,mappedFields,mappingCandidates,suggestedChoice,type GenericForm,type GenericMappingSelection} from './genericForm'

const props = defineProps<{form:GenericForm;disabled:boolean;presets?:GenericMappingSelection[]}>()
const emit = defineEmits<{accept:[selection:GenericMappingSelection]}>()
const section = ref('')
const fields = computed(()=>mappingCandidates(props.form,section.value))
const suggested = ()=>Object.fromEntries(fields.value.map(({id,candidates})=>[id,suggestedChoice(candidates)]))
const choices = ref(suggested())
const confirmed = ref(false)
const school = ref('')
const mapping = computed(()=>({form:props.form,choices:choices.value,section:section.value || undefined}))
const complete = computed(()=>fields.value.length>0 && mappedFields(mapping.value).every(item=>item.choice))
function chooseSection(event:Event) {
  section.value = (event.target as HTMLSelectElement).value
  choices.value = suggested()
  confirmed.value = false
}
function restore(index:number) {
  const preset = props.presets?.[index]
  if (!preset) return
  section.value = preset.section || ''
  choices.value = {...preset.choices}
  confirmed.value = false
}
const writable = computed(()=>canWriteMapping(mapping.value))
</script>

<template>
  <fieldset class="mapping" :disabled="disabled">
    <legend>核对原表字段位置</legend>
    <p>请对照 {{ form.name }} 核对下列位置和填写角色。未识别字段和已有内容仍需在原件中检查。</p>
    <label v-if="presets?.length">恢复已保存的字段位置
      <select @change="restore(Number(($event.target as HTMLSelectElement).value))">
        <option value="-1">选择草稿</option>
        <option v-for="(preset,i) in presets" :key="i" :value="i">{{ form.sections.find(s=>s.id===preset.section)?.label || '整表' }} · 草稿 {{ i+1 }}</option>
      </select>
    </label>
    <label v-if="form.sections.length">填写分区
      <select :value="section" @change="chooseSection">
        <option value="">请选择本次填写的分区</option>
        <option v-for="item in form.sections" :key="item.id" :value="item.id">{{ item.label }}</option>
      </select>
    </label>
    <label v-for="{id,candidates} in fields" :key="id">
      写入位置 · {{ candidates[0].field.label }}
      <select v-model="choices[id]" @change="confirmed=false">
        <option value="">待核对</option>
        <option v-for="(item,index) in candidates" :key="index" :value="String(index)" :disabled="!item.slot">
          {{ item.label }} · {{ item.slot ? item.slot.where : item.where+'（位置待核对）' }}
        </option>
        <option value="manual">留给人工填写</option>
      </select>
    </label>
    <details v-if="form.manual.length">
      <summary>查看保留的原文区域</summary>
      <ul><li v-for="(item,index) in form.manual" :key="index">{{ item.where }} · {{ item.text }}</li></ul>
    </details>
    <p v-if="complete && !writable">部分字段需手工填写或位置重叠，可在填写清单中核对后手工填入原件。</p>
    <label>原件适用学校全称（从个人画像补录时填写）
      <input v-model="school" maxlength="100" @input="confirmed=false">
    </label>
    <label><input v-model="confirmed" type="checkbox"> 我已对照原表确认写入位置和需人工核对的要求</label>
    <button type="button" :disabled="!complete || !confirmed" @click="emit('accept',{choices:{...choices},section:mapping.section,school:school.trim()})">
      使用已核对的位置填写
    </button>
  </fieldset>
</template>

<style scoped>
.mapping{border:1px solid #dce5f0;margin:1rem 0 0;padding:.7rem;min-width:0;overflow-wrap:anywhere}
.mapping label{display:block;margin:.55rem 0}
.mapping select{display:block;max-width:100%;margin-top:.2rem}
</style>
