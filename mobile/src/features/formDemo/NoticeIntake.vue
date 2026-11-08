<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {useImportDraftStore} from '../imports/draftStore'
import {analyzeNotice,applyNotice,matchAttachment,readNotice,suggestedTarget,type AttachmentMatch,type NoticeEvidence,type NoticeRequirements,type NoticeSelection} from './noticeIntake'

type FileRole = 'form' | 'proof' | 'instructions' | 'school' | 'unknown'
const props = defineProps<{busy:boolean; progress:Record<number,'editing'|'exported'>}>()
const emit = defineEmits<{
  (event:'invalidate'):void
  (event:'reset'):void
  (event:'accept',value:NoticeSelection):void
}>()
const draft = useImportDraftStore()
const text = ref(draft.text)
const source = ref('导入的通知正文')
const files = ref<File[]>([...draft.files])
const matches = ref<AttachmentMatch[]>([])
const noticeIndex = ref<number>()
const roles = ref<Record<number,FileRole>>({})
const scopes = ref<Record<number,string>>({})
const selected = ref(-1)
const inspected = ref<NoticeRequirements>()
const acknowledged = ref(false)
const accepted = ref(false)
const loading = ref(false)
const error = ref('')
const disabled = computed(()=>loading.value || props.busy)
const noticeFiles = computed(()=>files.value.flatMap((file,index)=>
  /\.(txt|docx)$/i.test(file.name) && !matches.value[index]?.scenario ? [{index,name:file.name}] : []))
const attachments = computed(()=>matches.value.flatMap((match,index)=>
  index===noticeIndex.value ? [] : [{match,index,role:roles.value[index] || 'unknown'}]))
const targets = computed(()=>attachments.value.flatMap(({match,index,role})=>
  role==='form' || (role==='unknown' && /\.(docx|xlsx)$/i.test(match.name))
    ? [{id:index,name:match.name,title:match.scenario?.title}] : []))
const formIndexes = computed(()=>attachments.value.flatMap(({match,index,role})=>role==='form' && match.scenario ? [index] : []))
const labels = {length:'字数校验',filename:'文件名',photo:'打印后贴照',review:'待人工核对'}
const roleLabels: Record<FileRole,string> = {
  form:'申请人填写',proof:'另附证明',instructions:'须知',school:'校方填写',unknown:'待确认用途',
}
const ruleEvidence = computed(()=>inspected.value?.evidence.filter(item=>item.kind!=='review') || [])
const scopeById = computed(()=>new Map(ruleEvidence.value.map(item=>{
  const suggestion = suggestedTarget(item,targets.value)
  return [item.id,scopes.value[item.id] ?? (suggestion===undefined?'':String(suggestion))]
})))
const unassigned = computed(()=>ruleEvidence.value.some(item=>scopeById.value.get(item.id)===''))
const manualReviews = computed(()=>inspected.value?.evidence.filter(item=>
  item.kind==='review' || scopeById.value.get(item.id)==='manual').length || 0)
const candidate = computed(()=>{
  const match = matches.value[selected.value]
  if (!match?.scenario || !inspected.value || !formIndexes.value.includes(selected.value)) return undefined
  const requirements = analyzeNotice(text.value,clause=>{
    const scope = scopeById.value.get(clause.id)
    return scope===String(selected.value) || scope==='all'
  })
  return {...applyNotice(match.scenario,requirements),requirements,attachment:match.name}
})

function pauseForm() {
  acknowledged.value = false
  accepted.value = false
  emit('invalidate')
}

function invalidate() {
  inspected.value = undefined
  selected.value = -1
  scopes.value = {}
  error.value = ''
  pauseForm()
}

async function setNotice(file: File,index?: number) {
  try {
    const content = await readNotice(file)
    text.value = content
    source.value = file.name
    noticeIndex.value = index
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : '通知读取失败。'
  }
}

async function loadNotice(file: File,index?: number) {
  invalidate()
  loading.value = true
  try { await setNotice(file,index) } finally { loading.value = false }
}

async function inventory() {
  loading.value = true
  try {
    if (files.value.length>10) throw Error('每次最多核对 10 个文件。')
    matches.value = await Promise.all(files.value.map(async file=>{
      if (!/\.(docx|xlsx)$/i.test(file.name)) return {name:file.name}
      try { return await matchAttachment(file) } catch { return {name:file.name,error:'本机无法核验此文件。'} }
    }))
    roles.value = Object.fromEntries(matches.value.flatMap((match,index)=>match.scenario?[[index,'form' as const]]:[]))
    if (text.value.trim()) return
    const txt = noticeFiles.value.filter(item=>/\.txt$/i.test(item.name))
    const namedWord = noticeFiles.value.filter(item=>/(通知|公告|通告).*\.docx$/i.test(item.name))
    const suggested = txt.length===1 ? txt[0] : !txt.length && namedWord.length===1 ? namedWord[0] : undefined
    if (suggested) await setNotice(files.value[suggested.index],suggested.index)
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : '附件核对失败。'
  } finally {
    loading.value = false
  }
}
onMounted(inventory)

function chooseNotice(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void loadNotice(file)
}

function chooseImportedNotice(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (!value) return
  const index = Number(value)
  void loadNotice(files.value[index],index)
}

function chooseAttachments(event: Event) {
  const next = Array.from((event.target as HTMLInputElement).files || [])
  if (next.length>10) {
    error.value = '每次最多核对 10 个文件。'
    return
  }
  invalidate()
  noticeIndex.value = undefined
  files.value = next
  matches.value = []
  emit('reset')
  void inventory()
}

function inspect() {
  invalidate()
  if (!text.value.trim() || text.value.length>30_000) {
    error.value = '请提供不超过 30,000 字的通知正文。'
    return
  }
  if (files.value.length>10) {
    error.value = '每次最多核对 10 个文件。'
    return
  }
  inspected.value = analyzeNotice(text.value)
  if (formIndexes.value.length===1) selected.value = formIndexes.value[0]
}

function changeRole(index: number,event: Event) {
  roles.value[index] = (event.target as HTMLSelectElement).value as FileRole
  if (!formIndexes.value.includes(selected.value)) selected.value = formIndexes.value.length===1 ? formIndexes.value[0] : -1
  scopes.value = {}
  pauseForm()
}

function setScope(item: NoticeEvidence,event: Event) {
  scopes.value[item.id] = (event.target as HTMLSelectElement).value
  pauseForm()
}

function pick(index: number) {
  selected.value = index
  pauseForm()
}

function accept() {
  if (disabled.value || accepted.value || !candidate.value || candidate.value.conflict || !acknowledged.value ||
      unassigned.value || inspected.value?.competition) return
  accepted.value = true
  emit('accept',{id:selected.value,scenario:candidate.value.scenario,requirements:candidate.value.requirements,
    attachment:candidate.value.attachment,manualReviews:manualReviews.value})
}
</script>

<template>
  <section class="intake" aria-label="通知与附件">
    <h2>1. 核对通知和附件</h2>
    <p>从导入页带入文字与已选文件。填写和导出在本机完成。</p>
    <label v-if="noticeFiles.length">从已选文件指定通知正文
      <select :value="noticeIndex ?? ''" :disabled="disabled" @change="chooseImportedNotice">
        <option value="" disabled>选择已导入的通知文件</option>
        <option v-for="file in noticeFiles" :key="file.index" :value="file.index">{{ file.name }}</option>
      </select>
    </label>
    <label>通知正文<textarea v-model="text" :disabled="disabled" rows="6" maxlength="30000" @input="source='手动编辑的通知正文'; invalidate()"></textarea></label>
    <label>选择通知文件（TXT 或 DOCX）<input type="file" accept=".txt,.docx" :disabled="disabled" @change="chooseNotice"></label>
    <label>选择申请表原件（DOCX 或 XLSX）<input type="file" multiple accept=".docx,.xlsx" :disabled="disabled" @change="chooseAttachments"></label>
    <ul v-if="files.length && !inspected"><li v-for="(file,index) in files" :key="index">{{ file.name }}</li></ul>
    <button type="button" :disabled="disabled" @click="inspect">{{ loading?'正在本机核对…':'核对通知与附件' }}</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="inspected && !loading">
      <div v-if="inspected.competitionEvidence">
        <p>该通知可能涉及赛事报名或材料提交，可在日程中跟进。<RouterLink to="/plan/schedule">转到日程安排</RouterLink></p>
        <p>{{ source }} · 第 {{ inspected.competitionEvidence.line }} 行 · {{ inspected.competitionEvidence.text }}</p>
      </div>
      <h3>附件清单</h3>
      <ul v-if="attachments.length">
        <li v-for="{match,index,role} in attachments" :key="index">
          <label v-if="match.scenario && role==='form'"><input type="radio" name="original" :checked="selected===index" :disabled="disabled" @change="pick(index)"> {{ match.name }} · {{ match.scenario.title }}</label>
          <p v-else>{{ match.name }} <template v-if="role==='unknown' || role==='form'">· {{ match.error || '待核对' }}</template></p>
          <small v-if="match.scenario && role==='form'">{{ progress[index]==='exported'?'已导出':progress[index]==='editing'?'填写中':'原表已核验，可填写' }}</small>
          <label>附件用途
            <select :aria-label="'附件用途 · '+match.name" :value="role" :disabled="disabled" @change="changeRole(index,$event)">
              <option v-for="(label,key) in roleLabels" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
        </li>
      </ul>
      <p v-if="!formIndexes.length && !inspected.competition">待核对：请选择能确认来源和版本的申请表原件。</p>
      <h3>通知依据</h3>
      <p v-if="!inspected.evidence.length">待核对：未识别到可引用的具体要求，继续前请检查原通知。</p>
      <ol v-else>
        <li v-for="item in inspected.evidence" :key="item.id">
          <small>{{ source }} · 第 {{ item.line }} 行 · {{ labels[item.kind] }}</small><div>{{ item.text }}</div>
          <label v-if="item.kind!=='review' && targets.length">适用附件
            <select :aria-label="'适用附件 · 第 '+item.line+' 行 · '+item.text" :value="scopeById.get(item.id)" :disabled="disabled" @change="setScope(item,$event)">
              <option value="">待确认适用附件</option>
              <option v-for="target in targets" :key="target.id" :value="String(target.id)">{{ target.name }}</option>
              <option v-if="targets.length>1" value="all">全部填写表</option>
              <option value="manual">待人工核对，暂不应用</option>
            </select>
          </label>
        </li>
      </ol>
      <p v-if="unassigned && targets.length && !inspected.competition" role="alert">请确认上方未分配的要求适用哪份附件，或标记待人工核对。</p>
      <p v-if="candidate?.conflict && !inspected.competition" role="alert">{{ candidate.attachment }} · {{ candidate.conflict }}</p>
      <template v-if="!inspected.competition">
        <label><input v-model="acknowledged" type="checkbox" :disabled="disabled" @change="accepted=false; emit('invalidate')"> 我已核对通知原文和需人工办理的要求</label>
        <button type="button" :disabled="disabled || accepted || !candidate || Boolean(candidate.conflict) || unassigned || !acknowledged" @click="accept">{{ accepted?'已启用该申请表':'按此通知填写选中原表' }}</button>
      </template>
    </template>
  </section>
</template>

<style scoped>
.intake{background:white;border:1px solid #dce5f0;border-radius:1rem;padding:1rem;margin-bottom:1rem}
.intake h2,.intake h3{margin:.25rem 0 .5rem}
.intake label{display:block;margin:.7rem 0;overflow-wrap:anywhere}
.intake textarea{display:block;width:100%;min-height:8rem;margin-top:.3rem;border:1px solid #bacce2;border-radius:.5rem;padding:.5rem}
.intake input[type=file],.intake select{display:block;max-width:100%;margin-top:.3rem}
.intake li{margin:.35rem 0;overflow-wrap:anywhere}
.intake small{color:#40577a}
.intake button{background:#eef5ff;border:1px solid #bacce2;border-radius:.55rem;color:#1a4782;padding:.55rem .7rem}
.intake button:disabled{opacity:.55}
</style>
