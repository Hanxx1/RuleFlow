<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {useImportDraftStore} from '../imports/draftStore'
import {analyzeNotice,applyNotice,matchAttachment,readNotice,type AttachmentMatch,type NoticeRequirements} from './noticeIntake'
import type {Scenario} from './scenarios'

const emit = defineEmits<{
  (event:'invalidate'):void
  (event:'accept',value:{scenario:Scenario;requirements:NoticeRequirements;attachment:string}):void
}>()
const draft = useImportDraftStore()
const text = ref(draft.text)
const source = ref('导入的通知正文')
const files = ref<File[]>(draft.files.filter(file=>/\.(xlsx|docx)$/i.test(file.name)))
const matches = ref<AttachmentMatch[]>([])
const selected = ref(-1)
const inspected = ref<NoticeRequirements>()
const acknowledged = ref(false)
const accepted = ref(false)
const loading = ref(false)
const error = ref('')
const candidate = computed(()=>{
  const scenario = matches.value[selected.value]?.scenario
  const requirements = inspected.value
  if (!scenario || !requirements) return undefined
  const distinct = new Set(matches.value.flatMap(item=>item.scenario?[item.scenario.id]:[]))
  if (distinct.size>1 && (requirements.naming || requirements.physicalPhoto || Object.keys(requirements.lengths).length)) {
    return {scenario,conflict:'检测到多份不同原表。请分别导入一份原表和适用的通知段落，避免混用要求。'}
  }
  return applyNotice(scenario,requirements)
})
const labels = {length:'字数校验',filename:'文件名',photo:'打印后贴照',review:'人工核对'}

function invalidate() {
  inspected.value = undefined
  matches.value = []
  selected.value = -1
  acknowledged.value = false
  accepted.value = false
  error.value = ''
  emit('invalidate')
}

async function loadNotice(file: File) {
  invalidate()
  loading.value = true
  try {
    text.value = await readNotice(file)
    source.value = file.name
  } catch (problem) {
    text.value = ''
    error.value = problem instanceof Error ? problem.message : '通知读取失败。'
  } finally {
    loading.value = false
  }
}
onMounted(()=>{
  const candidates = draft.files.filter(file=>/\.txt$/i.test(file.name))
  if (!text.value.trim() && candidates.length===1) void loadNotice(candidates[0])
})

function chooseNotice(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void loadNotice(file)
}

function chooseAttachments(event: Event) {
  invalidate()
  files.value = Array.from((event.target as HTMLInputElement).files || [])
}

async function inspect() {
  invalidate()
  if (!text.value.trim() || text.value.length>30_000) {
    error.value = '请提供不超过 30,000 字的通知正文。'
    return
  }
  loading.value = true
  try {
    inspected.value = analyzeNotice(text.value)
    if (files.value.length>10) throw Error('每次最多核对 10 个附件。')
    matches.value = await Promise.all(files.value.map(matchAttachment))
    const accepted = matches.value.flatMap((match,index)=>match.scenario?[index]:[])
    if (accepted.length===1) selected.value = accepted[0]
    if (!accepted.length && !inspected.value.competition) error.value = '待核对：请选择能确认来源和版本的申请表原件。'
  } catch (problem) {
    inspected.value = undefined
    error.value = problem instanceof Error ? problem.message : '附件核对失败。'
  } finally {
    loading.value = false
  }
}

function pick(index: number) {
  selected.value = index
  acknowledged.value = false
  accepted.value = false
  emit('invalidate')
}
function accept() {
  const requirements = inspected.value
  if (accepted.value || !requirements || !candidate.value || candidate.value.conflict || !acknowledged.value) return
  accepted.value = true
  emit('accept',{scenario:candidate.value.scenario,requirements,attachment:matches.value[selected.value].name})
}
</script>

<template>
  <section class="intake" aria-label="通知与附件">
    <h2>1. 核对通知和附件</h2>
    <p>从导入页带入文字与已选文件。填写和导出在本机完成。</p>
    <label>通知正文<textarea v-model="text" :disabled="loading" rows="6" maxlength="30000" @input="source='导入的通知正文'; invalidate()"></textarea></label>
    <label>选择通知文件（TXT 或 DOCX）<input type="file" accept=".txt,.docx" :disabled="loading" @change="chooseNotice"></label>
    <label>选择申请表原件（DOCX 或 XLSX）<input type="file" multiple accept=".docx,.xlsx" :disabled="loading" @change="chooseAttachments"></label>
    <ul v-if="files.length && !matches.length"><li v-for="(file,index) in files" :key="index">{{ file.name }}</li></ul>
    <button type="button" :disabled="loading" @click="inspect">{{ loading?'正在本机核对…':'核对通知与附件' }}</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="inspected && !loading">
      <p v-if="inspected.competition">通知可能涉及赛事报名或材料提交，可按通知在日程中跟进。<RouterLink to="/plan/schedule">转到日程安排</RouterLink></p>
      <h3>通知依据</h3>
      <p v-if="!inspected.evidence.length">待核对：未识别到可引用的具体要求，继续前请检查原通知。</p>
      <ol v-else>
        <li v-for="(item,index) in inspected.evidence" :key="index">
          <small>{{ source }} · 第 {{ item.line }} 行 · {{ labels[item.kind] }}</small><div>{{ item.text }}</div>
        </li>
      </ol>
      <h3 v-if="matches.length">附件匹配</h3>
      <ul>
        <li v-for="(match,index) in matches" :key="index">
          <label v-if="match.scenario"><input type="radio" name="original" :checked="selected===index" @change="pick(index)"> {{ match.name }} · {{ match.scenario.title }}</label>
          <p v-else>{{ match.name }} · {{ match.error }}</p>
        </li>
      </ul>
      <p v-if="candidate?.conflict" role="alert">{{ candidate.conflict }}</p>
      <label><input v-model="acknowledged" type="checkbox" @change="accepted=false; emit('invalidate')"> 我已核对通知原文和需人工办理的要求</label>
      <button type="button" :disabled="accepted || !candidate || Boolean(candidate.conflict) || !acknowledged" @click="accept">{{ accepted?'已启用该申请表':'按此通知填写选中原表' }}</button>
    </template>
  </section>
</template>

<style scoped>
.intake{background:white;border:1px solid #dce5f0;border-radius:1rem;padding:1rem;margin-bottom:1rem}
.intake h2,.intake h3{margin:.25rem 0 .5rem}
.intake label{display:block;margin:.7rem 0;overflow-wrap:anywhere}
.intake textarea{display:block;width:100%;min-height:8rem;margin-top:.3rem;border:1px solid #bacce2;border-radius:.5rem;padding:.5rem}
.intake input[type=file]{display:block;max-width:100%;margin-top:.3rem}
.intake li{margin:.35rem 0;overflow-wrap:anywhere}
.intake small{color:#40577a}
.intake button{background:#eef5ff;border:1px solid #bacce2;border-radius:.55rem;color:#1a4782;padding:.55rem .7rem}
.intake button:disabled{opacity:.55}
</style>
