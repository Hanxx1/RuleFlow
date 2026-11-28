<script setup lang="ts">
import {computed,defineAsyncComponent,onBeforeUnmount,onMounted,ref,shallowRef} from 'vue'
import {ApiError} from '../../core/http'
import {requirePrivacyReview} from '../../services/privacyGuard'
import {useImportBatchStore} from '../imports/batchStore'
import {FormContextInvalid,type FormContext} from '../imports/formContext'
import {readFormOriginal} from '../imports/formOriginal'
import {applyNotice,isExtendedOriginal,type NoticeSelection} from './noticeIntake'
import {useAccountStore} from '../../stores/account'
import {readFormDrafts,readDraftReference} from './savedFormDrafts'
import {restorePositions,storePositions} from './genericDraftMapping'
import GenericMappingReview from './GenericMappingReview.vue'
import {canWriteMapping,genericScenario,mappedFields,type GenericForm,type GenericMapping,type GenericMappingSelection} from './genericForm'
import {defaultNotice,isFillableSource,isOfficeSource,loadSavedNotice,loadSavedOriginal,originalProblem,recheckSavedForm,
  savedDraftKey,savedNoticeProblem,savedRules,type SavedRuleItem,type ScopeSelection} from './savedNotice'

const OriginalCopyEditor = defineAsyncComponent(()=>import('./OriginalCopyEditor.vue'))
const extended = shallowRef<{file:File;verify:()=>Promise<void>}>()
const props = defineProps<{batchId:string;busy:boolean;progress:Record<string,'editing'|'exported'>}>()
const emit = defineEmits<{invalidate:[];accept:[selection:NoticeSelection]}>()
const context = ref<FormContext>()
const batches = useImportBatchStore()
const uploadFile = ref<File>()
const uploadConsent = ref(false)
const uploadInput = ref<HTMLInputElement>()
const selectedId = ref('')
const selectedNotices = ref<Record<string,string>>({})
const selections = ref<Record<string,ScopeSelection>>({})
const excluded = ref<string[]>([])
const acknowledged = ref(false)
const busy = ref(false)
const error = ref('')
const account = useAccountStore()
const pendingMapping = shallowRef<{key:string;form:GenericForm;presets:GenericMappingSelection[]}>()
const former = new Map<string,{sourceId:string;name:string}>()
let request = 0

const targets = computed(()=>context.value?.sources.filter(isFillableSource) || [])
const target = computed(()=>targets.value.find(source=>source.source_id===selectedId.value))
const notices = computed(()=>context.value?.sources.filter(source=>source.source_id!==selectedId.value &&
  source.extraction.state==='available') || [])
const noticeId = computed(()=>context.value && target.value
  ? selectedNotices.value[target.value.source_id] ?? defaultNotice(context.value,target.value) : '')
const notice = computed(()=>notices.value.find(source=>source.source_id===noticeId.value))
const rules = computed(()=>context.value && target.value
  ? savedRules(context.value,notice.value,target.value.source_id,selections.value,excluded.value)
  : undefined)
const formProblem = computed(()=>target.value ? originalProblem(target.value) : '')
const noticeProblem = computed(()=>target.value ? savedNoticeProblem(target.value,notice.value) : '')
const disabled = computed(()=>props.busy || busy.value)
const canConfirmNotice = computed(()=>!noticeProblem.value && !rules.value?.unresolved)

function pause() {
  extended.value = undefined
  acknowledged.value = false
  error.value = ''
  pendingMapping.value = undefined
  emit('invalidate')
}

function showError(problem: unknown) {
  if (problem instanceof FormContextInvalid ||
      problem instanceof ApiError && (problem.status===401 || problem.status===404 || problem.code==='SOURCE_REFERENCE_INVALID')) {
    context.value = undefined
    pendingMapping.value = undefined
    emit('invalidate')
  }
  error.value = problem instanceof ApiError && problem.code==='SOURCE_REFERENCE_INVALID'
    ? '批次来源关系无法核验，已暂停读取。'
    : problem instanceof ApiError && problem.code==='IMPORT_BATCH_STALE' ? '来源仍在更新，请稍后重新读取。'
      : problem instanceof FormContextInvalid ? '来源响应无效，请重新读取。'
        : problem instanceof Error && !problem.message.startsWith('无法连接在线服务') && !problem.message.startsWith('请求失败 (')
          ? problem.message : '暂时无法读取来源，请检查账号或网络后重试。'
}

function applyContext(next: FormContext) {
  for (const source of next.sources.filter(isOfficeSource)) {
    if (source.document_ref) former.set(savedDraftKey(next.batch_id,source),{
      sourceId:source.source_id,
      name:`${source.name} · ${source.document_ref.sha256.slice(0,8)} · ${source.source_id.slice(-6)}`,
    })
  }
  context.value = next
  // Keep an explicit notice choice only while it is still available for this table.
  selectedNotices.value = Object.fromEntries(Object.entries(selectedNotices.value)
    .filter(([,id])=>!id || next.sources.some(source=>source.source_id===id && source.extraction.state==='available')))
  if (!targets.value.some(source=>source.source_id===selectedId.value)) {
    selectedId.value = targets.value.length===1 ? targets.value[0].source_id : ''
  }
}

async function refresh() {
  const version = ++request
  pause()
  busy.value = true
  try {
    const next = await loadSavedNotice(props.batchId)
    if (request===version) applyContext(next)
  } catch (problem) {
    if (request===version) showError(problem)
  } finally {
    if (request===version) busy.value = false
  }
}

function chooseNotice(event: Event) {
  selectedNotices.value[selectedId.value] = (event.target as HTMLSelectElement).value
  pause()
}

function chooseUpload(event: Event) {
  uploadFile.value = (event.target as HTMLInputElement).files?.[0]
  uploadConsent.value = false
}

async function addOriginal() {
  const file = uploadFile.value
  if (disabled.value || !file || !uploadConsent.value) return
  const version = ++request
  busy.value = true
  error.value = ''
  try {
    const review = await requirePrivacyReview('',[file],'',uploadConsent.value)
    if (request!==version ||
        review.unchecked_sources.length && !window.confirm('此文件尚未完成端侧扫描。确认已人工核对隐私并同意上传？')) return
    await batches.saveSources(props.batchId,{title:'',text:'',url:'',files:[file]})
    if (request!==version) return
    uploadFile.value = undefined
    uploadConsent.value = false
    if (uploadInput.value) uploadInput.value.value = ''
    await refresh()
  } catch (problem) {
    if (request===version) showError(problem)
  } finally {
    if (request===version) busy.value = false
  }
}

async function removeOriginal() {
  const source = target.value
  if (disabled.value || !source || !window.confirm('从当前批次移除此附件？填写值会保留在当前页面供对照。')) return
  const version = ++request
  busy.value = true
  error.value = ''
  try {
    await batches.removeSource(props.batchId,source.source_id)
    if (request===version) await refresh()
  } catch (problem) {
    if (request===version) showError(problem)
  } finally {
    if (request===version) busy.value = false
  }
}

function scopeValue(item: SavedRuleItem) {
  if (item.manual) return 'manual'
  if (item.needsScope) return ''
  return item.scope?.length===1 ? item.scope[0] : item.scope?.length ? 'all' : ''
}

function setScope(item: SavedRuleItem,event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (!value) delete selections.value[item.key]
  else if (rules.value) {
    const candidates = rules.value.targets.map(target=>target.id)
    selections.value[item.key] = {applyTo:value==='all' ? candidates : value==='manual' ? [] : [value],candidates,manual:value==='manual'}
  }
  pause()
}

async function openForm(mappingSelection?:GenericMappingSelection) {
  const snapshot = context.value
  const source = target.value
  const selectedNotice = notice.value
  const binding = rules.value
  if (disabled.value || !snapshot || !source || !binding || formProblem.value || binding.analysis.competition) return
  const key = savedDraftKey(snapshot.batch_id,source)
  if (mappingSelection && pendingMapping.value?.key!==key) return
  extended.value = undefined
  const version = ++request
  const scopes = {...selections.value}
  const exclusions = [...excluded.value]
  const confirmed = acknowledged.value && canConfirmNotice.value
  const notifyProblem = noticeProblem.value
  error.value = ''
  busy.value = true
  try {
    const checkBinding = (next:FormContext) => {
      const current = next.sources.find(item=>item.source_id===source.source_id)
      const currentNotice = next.sources.find(item=>item.source_id===selectedNotice?.source_id)
      if (!current || savedDraftKey(next.batch_id,current)!==key || next.case_id!==snapshot.case_id ||
          current.parent_reference_state!==source.parent_reference_state || current.parent_source_id!==source.parent_source_id ||
          savedRules(next,currentNotice,source.source_id,scopes,exclusions).signature!==binding.signature) {
        applyContext(next)
        pause()
        throw Error('这份表的原件、通知或适用范围已变化。填写值已保留，请重新核对。')
      }
      return current
    }
    const pinned = await loadSavedNotice(snapshot.batch_id)
    if (request!==version) return
    if (source.document_ref && isExtendedOriginal(source.document_ref.name)) {
      if (!confirmed || notifyProblem) throw Error(notifyProblem || '请先确认此附件的通知和适用范围。')
      const read = async (next:FormContext) => {
        if (request!==version || !acknowledged.value) throw Error('来源已切换，请重新核对。')
        const current = checkBinding(next)
        const blob = await readFormOriginal(next,current.source_id)
        const latest = await loadSavedNotice(snapshot.batch_id)
        if (request!==version || !acknowledged.value) throw Error('来源已切换，请重新核对。')
        checkBinding(latest)
        return blob
      }
      const blob = await read(pinned)
      extended.value = {file:new File([blob],source.document_ref.name),verify:async()=>{await read(await loadSavedNotice(snapshot.batch_id))}}
      return
    }
    const original = await loadSavedOriginal(pinned,checkBinding(pinned))
    if (request!==version) return
    const latest = await loadSavedNotice(snapshot.batch_id)
    if (request!==version) return
    const current = checkBinding(latest)
    const problem = originalProblem(current)
    if (problem) throw Error(problem)
    applyContext(latest)
    let mapping:GenericMapping | undefined
    if (original.generic) {
      if (!mappingSelection) {
        const presets:GenericMappingSelection[] = []
        const owner = account.user?.id
        const epoch = account.formDraftEpoch
        if (owner && epoch!==null) {
          try {
            for (const draft of await readFormDrafts({owner,epoch},snapshot.batch_id)) {
              const reference = readDraftReference(draft.key)
              if (!reference?.positions || JSON.stringify(JSON.parse(draft.key).slice(0,5))!==key) continue
              const preset = await restorePositions(original.generic,reference.positions)
              if (preset) presets.push(preset)
            }
          } catch {
            error.value = '保存的字段位置暂不能读取，可以重新核对原件。'
          }
        }
        if (request!==version || account.user?.id!==owner || epoch!==account.formDraftEpoch) return
        pendingMapping.value = {key,form:original.generic,presets}
        return
      }
      mapping = {form:original.generic,...mappingSelection}
      if (!mappedFields(mapping).length || mappedFields(mapping).some(item=>!item.choice)) throw Error('原件字段位置待核对，请重新检查。')
    } else if (mappingSelection) throw Error('原件映射方式已变化，请重新核对。')
    if (confirmed) {
      const candidates = binding.targets.map(item=>item.id)
      for (const item of binding.items) {
        if (!scopes[item.key] && item.scope) scopes[item.key] = {applyTo:item.scope,candidates}
      }
      selections.value = scopes
    }
    const scenario = mapping ? genericScenario(mapping,binding.requirements.physicalPhoto) : original.scenario
    if (!scenario) throw Error('无法确定原表填写方式。')
    const effective = applyNotice(scenario,binding.requirements)
    const currentKeys = new Set(latest.sources.map(item=>savedDraftKey(latest.batch_id,item)))
    const previousDrafts = [...former.entries()].filter(([old])=>old!==key && !currentKeys.has(old))
      .map(([old,item])=>({key:old,name:item.name}))
    const exportBlocked = notifyProblem || effective.conflict ||
      (binding.unresolved ? '请先确认通知要求分别适用哪些附件。'
        : !confirmed ? '请先核对适用于此表的通知要求，再确认导出。' : '') ||
      (mapping && !canWriteMapping(mapping) ? '还有无法安全写入的字段，可复制清单后在原件中填写。' : '')
    const draftKey = mapping ? JSON.stringify([...JSON.parse(key),await storePositions(mapping)]) : key
    if (request!==version) return
    pendingMapping.value = undefined
    emit('accept',{
      id:mapping ? key+':'+JSON.stringify([mapping.section,mappedFields(mapping).map(item=>item.choice)]) : key,
      draftKey,currentDraftKeys:[...currentKeys],previousDrafts,
      caseId:latest.case_id,genericMapping:mapping,progressId:key,
      scenario:effective.scenario,attachment:source.name,
      requirements:binding.requirements,
      manualReviews:binding.requirements.evidence.filter(item=>item.kind==='review').length,
      exportBlocked,
      verifyExport:async()=>{
        try {
          const rechecked = await loadSavedNotice(snapshot.batch_id)
          if (request!==version) throw Error('填写上下文已切换，请重新核对。')
          const recheck = (next: FormContext) => {
            if (next.case_id!==latest.case_id) throw Error('关联事项已变化。填写值已保留，请重新读取并核对。')
            return recheckSavedForm(next,source,key,selectedNotice?.source_id || '',binding.signature,scopes,exclusions)
          }
          const current = recheck(rechecked)
          await readFormOriginal(rechecked,current.source_id)
          const latestContext = await loadSavedNotice(snapshot.batch_id)
          if (request!==version) throw Error('填写上下文已切换，请重新核对。')
          recheck(latestContext)
        } catch (problem) {
          if (request===version && (problem instanceof FormContextInvalid ||
            problem instanceof ApiError && (problem.status===401 || problem.code==='SOURCE_REFERENCE_INVALID' || problem.code==='BATCH_NOT_FOUND'))) {
            showError(problem)
          }
          throw problem
        }
      },
    })
  } catch (problem) {
    if (request===version) {
      if (problem instanceof ApiError && problem.code==='DOCUMENT_CONTENT_MISSING') {
        error.value = '这份原件已缺失，请重新导入。'
      } else showError(problem)
    }
  } finally {
    if (request===version) busy.value = false
  }
}

onMounted(refresh)
onBeforeUnmount(()=>{request++})
</script>

<template>
  <section class="panel" aria-label="已保存通知与附件">
    <h2>核对已保存通知与附件</h2>
    <div class="actions">
      <button type="button" :disabled="disabled" @click="refresh">重新读取来源</button>
    </div>
    <p v-if="busy" role="status">正在核对保存的来源和原件…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="context">
      <h3>申请表候选</h3>
      <p v-if="!targets.length">没有可核对的申请表原件，请从来源页核对。</p>
      <ul>
        <li v-for="item in targets" :key="item.source_id">
          <label>
            <input v-model="selectedId" type="radio" name="saved-original" :value="item.source_id"
              :disabled="disabled || excluded.includes(item.source_id)" @change="pause">
            {{ item.name }} <small>· 来源 {{ item.source_id.slice(-6) }}</small>
          </label>
          <p v-if="originalProblem(item)">{{ originalProblem(item) }}</p>
          <p v-else-if="item.parent_reference_state==='missing'">父来源待核对</p>
          <p v-else-if="progress[savedDraftKey(batchId,item)]">{{ progress[savedDraftKey(batchId,item)]==='exported'?'已导出':'填写中' }}</p>
          <label><input v-model="excluded" type="checkbox" :value="item.source_id" :disabled="disabled"
            @change="if (excluded.includes(selectedId)) selectedId=''; pause()"> 此附件不用于填写 · {{ item.name }}</label>
        </li>
      </ul>
      <details>
        <summary>移除或补充本批次原件</summary>
        <p>请先移除需要替换的附件，再上传正确版本。当前页面会保留旧填写值供对照。</p>
        <button v-if="target" type="button" :disabled="disabled" @click="removeOriginal">移除所选附件</button>
        <label>选择补充原件
          <input ref="uploadInput" type="file" accept=".docx,.xlsx,.txt,.xls,.pdf,.png,.jpg,.jpeg" :disabled="disabled" @change="chooseUpload">
        </label>
        <label v-if="uploadFile"><input v-model="uploadConsent" type="checkbox" :disabled="disabled">
          我已核对该文件的隐私并同意上传到当前账户
        </label>
        <button type="button" :disabled="disabled || !uploadConsent || !uploadFile" @click="addOriginal">上传补充原件</button>
      </details>
      <template v-if="target && rules">
        <label>适用通知
          <select :value="noticeId" :disabled="disabled" @change="chooseNotice">
            <option value="">选择已保存通知</option>
            <option v-for="item in notices" :key="item.source_id" :value="item.source_id">{{ item.name }}</option>
          </select>
        </label>
        <details v-if="notice">
          <summary>查看已保存通知原文</summary>
          <pre>{{ notice.text }}</pre>
        </details>
        <p v-if="noticeProblem" class="warning">{{ noticeProblem }}</p>
        <p v-if="notice?.text_origin==='legacy_text'">历史粘贴正文没有正式原文行，要求待核对。</p>
        <ol v-if="rules.items.length">
          <li v-for="item in rules.items" :key="item.id">
            <small v-if="item.lineId">原文第 {{ item.lineNumber }} 行{{ item.locator ? ' · '+item.locator : '' }}</small>
            <small v-else>无正式行引用 · 待核对</small>
            <p>{{ item.text }}</p>
            <label v-if="item.kind!=='review'">适用附件 · {{ item.text }}
              <select :value="scopeValue(item)" :disabled="disabled" @change="setScope(item,$event)">
                <option value="">待确认适用附件</option>
                <option v-for="option in rules.targets" :key="option.id" :value="option.id">{{ option.name }} · {{ option.id.slice(-6) }}</option>
                <option v-if="rules.targets.length>1" value="all">以上全部申请表</option>
                <option value="manual">待人工办理，暂不应用到表格</option>
              </select>
            </label>
          </li>
        </ol>
        <p v-if="rules.unresolved" class="warning">还有要求的适用附件待核对，确认前可以填写草稿。</p>
        <p v-if="rules.analysis.competition">
          {{ rules.analysis.competitionEvidence?.text }} <RouterLink to="/plan/schedule">转到日程安排</RouterLink>
        </p>
        <template v-else>
          <label v-if="canConfirmNotice">
            <input v-model="acknowledged" type="checkbox" :disabled="disabled" @change="extended=undefined; emit('invalidate')">
            我已核对这份表的通知原文及提交要求
          </label>
          <button type="button" :disabled="disabled || Boolean(formProblem)" @click="openForm()">核验并填写选中原表</button>
          <GenericMappingReview v-if="pendingMapping" :key="pendingMapping.key" :form="pendingMapping.form" :presets="pendingMapping.presets"
            :disabled="disabled" @accept="openForm"/>
        </template>
      </template>
    </template>
    <OriginalCopyEditor v-if="extended" :key="request" :file="extended.file" :verify="extended.verify" />
  </section>
</template>

<style scoped>
.panel{background:white;border:1px solid #dce5f0;border-radius:1rem;padding:1rem;margin-bottom:1rem}
.actions{display:flex;align-items:center;flex-wrap:wrap;gap:.7rem}
li{margin-bottom:.65rem;overflow-wrap:anywhere}
label{display:block;margin:.45rem 0}
select{display:block;max-width:100%;margin-top:.25rem}
pre{max-height:16rem;overflow:auto;white-space:pre-wrap}
.warning,[role=alert]{color:#8a4516}
</style>
