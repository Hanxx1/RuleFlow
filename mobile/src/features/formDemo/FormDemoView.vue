<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,shallowRef,watch} from 'vue'
import {useAccountStore} from '../../stores/account'
import {loadWorkspace} from '../../services/clientWorkspace'
import {useImportDraftStore} from '../imports/draftStore'
import NoticeIntake from './NoticeIntake.vue'
import SavedNoticeIntake from './SavedNoticeIntake.vue'
import AccountProfileFill from './AccountProfileFill.vue'
import AccountAwardFill from './AccountAwardFill.vue'
import ApplicationReasonDraft from './ApplicationReasonDraft.vue'
import {experienceSource,loadExperiences} from '../experience/archive'
import {reviewAccountProfile,staleProfileLabels,type ProfileCandidate} from './accountFormProfile'
import {awardCandidates,currentAward,retainAwardUses,type AwardUse} from './accountAwardFill'
import {reasonAwards,type ReasonVersion} from './reasonDraft'
import {exportGenericForm,mappedFields} from './genericForm'
import {createOfficeDelivery,officeFilename} from './officeDelivery'
import {prepareVaultFormArchive,VaultArchiveUncertain,type VaultArchiveReceipt} from './vaultFormArchive'
import {noticeFilename,type NoticeSelection} from './noticeIntake'
import {clearFormDrafts,DraftRevisionConflict,DraftSessionExpired,draftRetentionDays,draftRetentionMs,
  observeDraftSessionRevocation,readDraftReference,readFormDrafts,recoverableFields,
  saveFormDraft,type DraftSession,type SavedFormDraft} from './savedFormDrafts'
import {avatarUrl,buildForm} from './exportForm'
import {awardReason,awardSlots,nextAwardSlot,readAward,writeAward,type DemoAward} from './demoAwards'
import {loadDemoProfile,profileKey,resolveDemoProfile,updateDemoProfile,type DemoOwner,type DemoProfile,type FormProfileOwner} from './demoProfile'
import {exampleValues,isCompetitionNotice,leaveDays,proposedFilename,reviewForm,scenarioFields,scenarios,validateFilename,type FormValues,type Scenario} from './scenarios'

const props = defineProps<{fromNotice?:boolean;savedBatchId?:string}>()
const account = useAccountStore()
const importDraft = useImportDraftStore()
const owner = ref<FormProfileOwner>(props.fromNotice?'local:notice':'demo:forms')
const intake = ref<NoticeSelection>()
const intakeKey = ref(0)
const persistAllowed = computed(()=>!props.savedBatchId && !intake.value?.genericMapping && (!props.fromNotice || !account.signedIn))
const profile = ref<DemoProfile>({revision:0,values:{},awards:[]})
const ready = ref(false)
const saving = ref(false)
const completion = ref<string[]>([])
const showAll = ref(false)
let loadVersion = 0
const scenario = ref(scenarios[0])
const values = ref<FormValues>({})
const nameOverride = ref('')
const photo = ref('')
const photoInput = ref<File>()
const zoom = ref(1)
const vertical = ref(50)
const notice = ref('')
const preview = ref(false)
const confirmation = shallowRef<ReturnType<typeof createOfficeDelivery>>()
const verifiedFile = shallowRef<{filename:string;bytes:number}>()
const vaultConsent = ref(false)
const vaultLinkCase = ref(false)
const archivedFile = shallowRef<VaultArchiveReceipt>()
const archiveUncertain = ref(false)
watch(confirmation,()=>{
  verifiedFile.value = undefined
  archivedFile.value = undefined
  archiveUncertain.value = false
  vaultConsent.value = false
  vaultLinkCase.value = false
},{flush:'sync'})
const reveal = ref(false)
const message = ref('')
const problem = ref('')
const imageVersion = ref(0)
const archive = computed(()=>profile.value.awards)
const reasonSuggestion = ref('')
const acceptedReason = ref<ReasonVersion>()
const reasonEditorKey = ref(0)
const profileFields = ref<Record<string,ProfileCandidate>>({})
const awardUses = ref<AwardUse[]>([])
const reasonSources = computed(()=>reasonAwards(awardUses.value))
const awardSources = computed(()=>Object.fromEntries(awardUses.value.flatMap(use=>
  Object.keys(use.fields).map(id=>[id,use.source]))))
const drafts = new Map<string,{values:FormValues;photo:string;name:string;
  profileFields?:Record<string,ProfileCandidate>;awardUses?:AwardUse[];acceptedReason?:ReasonVersion}>()
const attachmentProgress = ref<Record<string,'editing'|'exported'>>({})
const exporting = ref(false)
const priorDraftKey = ref('')
const carriedFields = ref<string[]>([])
const savedDrafts = ref<SavedFormDraft[]>([])
const draftRevisions = new Map<string,number>()
const draftBusy = ref(false)
const draftConflict = ref(false)
const draftError = ref('')
const draftMessage = ref('')
let formVersion = 0
let mounted = true
let draftRequest = 0
let draftExpiryTimer: ReturnType<typeof setTimeout> | undefined
let stopDraftRevocations: (()=>void) | undefined
onBeforeUnmount(()=>{
  mounted=false
  stopDraftRevocations?.()
  clearTimeout(draftExpiryTimer)
})
watch(savedDrafts,records=>{
  clearTimeout(draftExpiryTimer)
  if (!records.length) return
  const expires = Math.min(...records.map(record=>record.savedAt+draftRetentionMs))
  draftExpiryTimer = setTimeout(()=>{
    savedDrafts.value = savedDrafts.value.filter(record=>Date.now()<record.savedAt+draftRetentionMs)
  },Math.max(0,expires-Date.now()))
})
const priorDrafts = computed(()=>{
  if (!intake.value?.currentDraftKeys) return []
  const items = new Map((intake.value.previousDrafts || []).filter(item=>drafts.has(item.key))
    .map(item=>[item.key,item.name]))
  for (const item of savedDrafts.value) {
    if (intake.value.currentDraftKeys.includes(item.key) || items.has(item.key)) continue
    const reference = readDraftReference(item.key)
    if (!reference) continue
    const title = scenarios.find(scenario=>scenario.id===item.scenarioId)?.title
    items.set(item.key,`${title} · ${reference.sha256.slice(0,8)} · ${reference.sourceId.slice(-6)}`)
  }
  return [...items.entries()].map(([key,name])=>({key,name}))
})
const priorValues = computed(()=>drafts.get(priorDraftKey.value)?.values ||
  savedDrafts.value.find(item=>item.key===priorDraftKey.value)?.values || {})
const priorReason = computed(()=>drafts.get(priorDraftKey.value)?.values.reason)
const priorAwardFields = computed(()=>new Set((drafts.get(priorDraftKey.value)?.awardUses || [])
  .flatMap(use=>Object.keys(use.fields))))
const comparableFields = computed(()=>scenarioFields(scenario.value)
  .filter(field=>field.id!=='reason' && priorValues.value[field.id]?.trim() && !priorAwardFields.value.has(field.id)))
const draftFields = computed(()=>recoverableFields(scenario.value))
const currentSavedDraft = computed(()=>savedDrafts.value.find(item=>item.key===intake.value?.draftKey))
const draftExpiryLabel = computed(()=>currentSavedDraft.value
  ? new Date(currentSavedDraft.value.savedAt+draftRetentionMs).toLocaleString('zh-CN') : '')


const review = computed(()=>reviewForm(scenario.value,values.value,Boolean(photo.value)))
const count = computed(()=>Object.keys(review.value.errors).length)
const groups = computed(()=>scenario.value.groups.map(group=>({
  ...group,fields:showAll.value?group.fields:group.fields.filter(field=>completion.value.includes(field.id)),
})).filter(group=>group.fields.length))
watch(review,result=>{
  for (const id of Object.keys(result.errors)) if (!completion.value.includes(id)) completion.value.push(id)
})
const requiredStem = computed(()=>intake.value ? noticeFilename(intake.value.requirements,values.value) : '')
const suggestedStem = computed(()=>{
  if (props.fromNotice) return requiredStem.value || intake.value?.attachment.replace(/\.(docx|xlsx)$/i,'') || ''
  return proposedFilename(scenario.value,values.value)
})
const filename = computed(()=>nameOverride.value || suggestedStem.value)
const filenameError = computed(()=>{
  if (intake.value?.requirements.naming && !requiredStem.value) return '请先补齐通知规定的命名字段。'
  if (requiredStem.value && filename.value!==requiredStem.value) return '文件名须与通知识别出的命名要求一致。'
  return validateFilename(filename.value)
})
const filenamePreview = computed(()=>officeFilename(scenario.value.format,filename.value,!props.fromNotice))
const handoffRequests = computed(()=>intake.value?.requirements.evidence.filter(item=>
  item.kind==='review' || item.kind==='photo') ?? [])
const days = computed(()=>leaveDays(values.value))
const competition = computed(()=>isCompetitionNotice(notice.value))

function changed() {
  formVersion++
  for (const key of Object.keys(profileFields.value)) {
    if (values.value[key]!==profileFields.value[key].value) delete profileFields.value[key]
  }
  awardUses.value = retainAwardUses(awardUses.value,values.value)
  if (!values.value.reason?.trim()) acceptedReason.value = undefined
  draftMessage.value = ''
  confirmation.value = undefined
  if (intake.value) attachmentProgress.value[intake.value.progressId ?? intake.value.id] = 'editing'
  message.value = ''
  problem.value = ''
}

function rememberDraft(key: string) {
  drafts.set(key,{values:{...values.value},photo:photo.value,name:nameOverride.value,
    profileFields:{...profileFields.value},awardUses:awardUses.value,acceptedReason:acceptedReason.value})
}

function clearDrafts() {
  drafts.clear()
  draftRevisions.clear()
  attachmentProgress.value = {}
}

function select(next: Scenario, saveCurrent = true, draftKey = next.id) {
  if (saveCurrent) rememberDraft(scenario.value.id)
  scenario.value = next
  const draft = drafts.get(draftKey)
  values.value = draft ? {...draft.values} : intake.value?.genericMapping ? {} : resolveDemoProfile(next,profile.value)
  profileFields.value = {...draft?.profileFields}
  awardUses.value = draft?.awardUses || []
  photo.value = draft?.photo || ''
  photoInput.value = undefined
  imageVersion.value++
  zoom.value = 1
  vertical.value = 50
  nameOverride.value = draft?.name || ''
  reasonSuggestion.value = ''
  acceptedReason.value = draft?.acceptedReason
  reasonEditorKey.value++
  preview.value = false
  reveal.value = false
  showAll.value = false
  completion.value = Object.keys(review.value.errors)
  changed()
  if (intake.value && draft) message.value = '已恢复这份附件在当前页面的填写内容，请重新确认导出。'
}

async function switchOwner(next: FormProfileOwner) {
  const version = ++loadVersion
  owner.value = next
  ready.value = false
  saving.value = false
  clearDrafts()
  draftRequest++
  draftBusy.value = false
  savedDrafts.value = []
  priorDraftKey.value = ''
  carriedFields.value = []
  draftConflict.value = false
  draftError.value = ''
  draftMessage.value = ''
  profile.value = {revision:0,values:{},awards:[]}
  select(scenario.value,false)
  if (!persistAllowed.value) {
    ready.value = true
    return
  }
  try {
    const loaded = await loadDemoProfile(next)
    if (loadVersion!==version) return
    profile.value = loaded
    select(scenario.value,false)
  } catch {
    if (loadVersion!==version) return
    select(scenario.value,false)
    problem.value = '本机资料无法读取，可以继续填写当前表。'
  } finally {
    if (loadVersion===version) ready.value = true
  }
}
onMounted(()=>{
  void switchOwner(owner.value)
  if (props.fromNotice) stopDraftRevocations = observeDraftSessionRevocation((revokedOwner,epoch)=>{
    if (account.user?.id!==revokedOwner || account.formDraftEpoch===null || account.formDraftEpoch>=epoch) return
    account.formDraftEpoch = null
    resetRevokedDraftPage()
    draftError.value = new DraftSessionExpired().message
  })
})

function invalidateIntake() {
  if (intake.value) rememberDraft(intake.value.draftKey ?? 'notice:'+intake.value.id)
  intake.value = undefined
  preview.value = false
  draftMessage.value = ''
  draftRequest++
  draftBusy.value = false
  changed()
}

function resetRevokedDraftPage() {
  invalidateIntake()
  intakeKey.value++
  void switchOwner('local:notice')
}

async function acceptIntake(selection: NoticeSelection) {
  if (intake.value) invalidateIntake()
  const batch = props.savedBatchId
  const key = selection.draftKey ?? 'notice:'+selection.id
  if (batch && selection.draftKey) {
    const reading = runDraftAction(session=>readFormDrafts(session,batch))
    const request = draftRequest
    const records = await reading
    if (!mounted || request!==draftRequest) return
    savedDrafts.value = records ?? []
  }
  intake.value = selection
  priorDraftKey.value = ''
  carriedFields.value = []
  const saved = savedDrafts.value.find(item=>item.key===key && item.scenarioId===selection.scenario.id)
  if (!draftRevisions.has(key)) draftRevisions.set(key,saved?.revision ?? 0)
  const restored = saved && !drafts.has(key)
  if (restored) drafts.set(key,{values:{...saved.values},photo:'',name:''})
  select(selection.scenario,false,key)
  if (restored) message.value = '已恢复此原件版本保存的草稿。请补齐本次资料并重新确认导出。'
}

async function runDraftAction<T>(action:(session:DraftSession)=>Promise<T>): Promise<T | undefined> {
  const owner = account.user?.id
  const epoch = account.formDraftEpoch
  if (!owner || epoch===null) {
    draftError.value = '本机草稿当前不可用。请检查浏览器存储后重新登录。'
    return
  }
  const request = ++draftRequest
  const current = ()=>mounted && draftRequest===request && account.user?.id===owner
  draftBusy.value = true
  draftError.value = ''
  draftMessage.value = ''
  draftConflict.value = false
  try {
    const result = await action({owner,epoch})
    if (current() && account.formDraftEpoch===epoch) return result
  } catch (error) {
    if (!current()) return
    draftConflict.value = error instanceof DraftRevisionConflict
    if (error instanceof DraftSessionExpired) {
      account.formDraftEpoch = null
      resetRevokedDraftPage()
    }
    draftError.value = error instanceof Error ? error.message : '本机草稿无法操作，当前填写内容仍在。'
  } finally {
    if (current()) draftBusy.value = false
  }
}

async function saveDraftProgress() {
  const batch = props.savedBatchId
  const key = intake.value?.draftKey
  if (!batch || !key || exporting.value || draftBusy.value) return
  const manualValues = Object.fromEntries(Object.entries(values.value)
    .filter(([id])=>!profileFields.value[id] && !awardSources.value[id]))
  const result = await runDraftAction(session=>
    saveFormDraft(session,batch,key,scenario.value.id,manualValues,draftRevisions.get(key) ?? 0))
  if (!result) return
  draftRevisions.set(key,result.saved.revision)
  savedDrafts.value = result.drafts
  draftMessage.value = '已保存当前原件的草稿字段。'
}

async function reopenSavedProgress() {
  const batch = props.savedBatchId
  const key = intake.value?.draftKey
  if (!batch || !key || exporting.value || draftBusy.value) return
  const records = await runDraftAction(session=>readFormDrafts(session,batch))
  if (!records) return
  savedDrafts.value = records
  const saved = records.find(item=>item.key===key && item.scenarioId===scenario.value.id)
  if (saved && !window.confirm('读取已保存的版本？本页对应的手填字段会被替换。')) {
    draftConflict.value = true
    return
  }
  draftRevisions.set(key,saved?.revision ?? 0)
  if (saved) {
    for (const {id} of recoverableFields(scenario.value)) {
      if (saved.values[id]!==undefined) {
        values.value[id] = saved.values[id]
        delete profileFields.value[id]
      } else if (!profileFields.value[id]) delete values.value[id]
    }
    changed()
    rememberDraft(key)
  }
  draftMessage.value = saved ? '已读取保存的版本，请重新核对。' : '此原件暂无保存记录，当前输入仍在。'
}

async function clearDraftProgress() {
  const batch = props.savedBatchId
  if (!batch || exporting.value || draftBusy.value ||
      !window.confirm('清除本批次在此设备保存的草稿？当前填写内容会留在页面。')) return
  const cleared = await runDraftAction(async session=>{
    await clearFormDrafts(session,batch)
    return true
  })
  if (!cleared) return
  draftRevisions.clear()
  savedDrafts.value = []
  draftMessage.value = '本批次保存的草稿已清除。'
}
function carryPreviousFields() {
  const allowed = new Set(comparableFields.value.map(field=>field.id))
  for (const id of carriedFields.value) if (allowed.has(id)) values.value[id]=priorValues.value[id]
  carriedFields.value = []
  showAll.value = true
  changed()
}

function fillFromAccountProfile(candidates: ProfileCandidate[]) {
  if (exporting.value) return
  const applied = candidates.filter(item=>!values.value[item.id]?.trim())
  for (const item of applied) {
    values.value[item.id] = item.value
    profileFields.value[item.id] = item
  }
  if (!applied.length) return
  completion.value = [...new Set([...completion.value,...applied.map(item=>item.id)])]
  changed()
  message.value = '已从当前账户的本机画像带入 '+applied.map(item=>item.label).join('、')+'。请核对本次填写值。'
}

function clearProfileFields() {
  for (const id of Object.keys(profileFields.value)) {
    if (values.value[id]===profileFields.value[id].value) delete values.value[id]
  }
  profileFields.value = {}
  changed()
}

function fillFromAccountAward(use:AwardUse) {
  const ids = Object.keys(use.fields)
  if (exporting.value || ids.some(id=>values.value[id]?.trim())) return
  Object.assign(values.value,use.fields)
  awardUses.value = [...awardUses.value,use]
  completion.value = [...new Set([...completion.value,...ids])]
  changed()
  message.value = '已带入奖项「'+use.entry.title+'」，请核对本次申报要求。'
}

function clearAwardFields() {
  for (const id of Object.keys(awardSources.value)) delete values.value[id]
  awardUses.value = []
  changed()
}

watch([()=>props.fromNotice,()=>props.savedBatchId],([enabled])=>{
  invalidateIntake()
  intakeKey.value++
  void switchOwner(enabled?'local:notice':'demo:forms')
})
watch(()=>account.user?.id,()=>{
  if (!props.fromNotice) return
  invalidateIntake()
  importDraft.reset()
  intakeKey.value++
  void switchOwner('local:notice')
})

function fillExamples() {
  for (const field of scenarioFields(scenario.value)) {
    if (!values.value[field.id]?.trim() && exampleValues[scenario.value.id][field.id]) {
      values.value[field.id] = exampleValues[scenario.value.id][field.id]
    }
  }
  if (scenario.value.photo==='embedded' && !photo.value) photo.value = avatarUrl
  changed()
}

async function saveProfile(edit: (previous: DemoProfile)=>DemoProfile, success: string) {
  if (saving.value || !ready.value) return false
  const identity = owner.value
  const version = loadVersion
  saving.value = true
  problem.value = ''
  try {
    const saved = await updateDemoProfile(identity,profile.value.revision,edit)
    if (version!==loadVersion) return false
    profile.value = saved
    message.value = success
    return true
  } catch (error) {
    if (version!==loadVersion) return false
    problem.value = error instanceof Error ? error.message : '本机资料保存失败。'
    try {
      const loaded = await loadDemoProfile(identity)
      if (version===loadVersion) profile.value = loaded
    } catch { /* Keep the draft editable. */ }
    return false
  } finally {
    if (version===loadVersion) saving.value = false
  }
}

async function saveCompletion() {
  if (count.value) return
  if (!persistAllowed.value) {
    preview.value = true
    return
  }
  const data = {...values.value}
  const current = scenario.value
  const additions: FormValues = {}
  for (const field of scenarioFields(current)) {
    const key = profileKey(current,field)
    if (key && data[field.id]?.trim()) additions[key] = data[field.id].trim()
  }
  const selected = current.id==='scholarship'
    ? awardSlots.map(slot=>readAward(data,slot)).filter((award): award is DemoAward=>Boolean(award))
    : []
  const saved = await saveProfile(previous=>{
    const awards = [...previous.awards]
    for (const award of selected) {
      if (!awards.some(item=>item.date===award.date && item.name===award.name && item.issuer===award.issuer)) awards.push(award)
    }
    return {...previous,values:{...previous.values,...additions},awards:awards.slice(-12)}
  },'可复用资料已保存在本机。仅用于本次的内容保留在当前草稿。')
  if (saved) {
    completion.value = []
    preview.value = true
  }
}

async function clearRemembered() {
  if (props.fromNotice && !window.confirm('清除此浏览器保存的可复用填表资料和当前未导出的草稿？')) return
  const success = props.fromNotice?'此浏览器保存的填表资料已清除。':'本机演示资料已清除。'
  if (!await saveProfile(previous=>({...previous,values:{},awards:[]}),success)) return
  clearDrafts()
  select(scenario.value,false)
  message.value = success
}

function storeAward(slot: number) {
  const award = readAward(values.value,slot)
  if (!award) return
  void saveProfile(previous=>{
    const exists = previous.awards.some(item=>item.date===award.date && item.name===award.name && item.issuer===award.issuer)
    return {...previous,awards:exists?previous.awards:[...previous.awards,award].slice(-12)}
  },'此获奖记录已保存到本机演示档案。')
}

function applyAward(award: DemoAward) {
  const next = writeAward(values.value,award)
  if (next) {
    values.value = next
    changed()
  }
}

function suggestReason() {
  const selected = awardSlots.map(slot=>readAward(values.value,slot)).filter((award): award is DemoAward=>Boolean(award))
  reasonSuggestion.value = awardReason(selected)
}

function useReason() {
  values.value.reason = reasonSuggestion.value
  reasonSuggestion.value = ''
  changed()
}

function acceptReason(version:ReasonVersion) {
  if (exporting.value) return
  acceptedReason.value = version
  values.value.reason = version.text
  if (!completion.value.includes('reason')) completion.value.push('reason')
  changed()
}

function confirmManualReason() {
  if (!acceptedReason.value || values.value.reason===acceptedReason.value.text) return
  acceptedReason.value = undefined
  changed()
}

async function cropPhoto() {
  const file = photoInput.value
  if (!file) return
  const version = ++imageVersion.value
  changed()
  photo.value = ''
  try {
    if (!['image/jpeg','image/png'].includes(file.type) || file.size > 5_000_000) throw Error('请选择 5 MB 以内的 PNG 或 JPEG 演示图片。')
    const image = await createImageBitmap(file)
    try {
      if (version !== imageVersion.value) return
      if (image.width < 100 || image.height < 140) throw Error('图片尺寸过小，至少需要 100 × 140 像素。')
      const canvas = document.createElement('canvas')
      canvas.width = 250
      canvas.height = 350
      const context = canvas.getContext('2d')
      if (!context) throw Error('当前浏览器无法裁切照片。')
      const scale = Math.max(canvas.width/image.width,canvas.height/image.height)*zoom.value
      const width = image.width*scale
      const height = image.height*scale
      context.fillStyle = '#fff'
      context.fillRect(0,0,250,350)
      context.drawImage(image,(250-width)/2,(350-height)*vertical.value/100,width,height)
      photo.value = canvas.toDataURL('image/png')
    } finally {
      image.close()
    }
  } catch (error) {
    if (version === imageVersion.value) problem.value = error instanceof Error ? error.message : '无法读取图片。'
  }
}

function choosePhoto(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.[0]) return
  photoInput.value = input.files[0]
  void cropPhoto()
  input.value = ''
}

function useAvatar() {
  imageVersion.value++
  photoInput.value = undefined
  photo.value = avatarUrl
  changed()
}

function confirmOutput(event:Event) {
  confirmation.value = undefined
  if (!(event.target as HTMLInputElement).checked) return
  const template = scenario.value
  const mapping = intake.value?.genericMapping
  const confirmedValues = Object.freeze({...values.value})
  const image = photo.value
  const stem = filename.value
  const demo = !props.fromNotice
  confirmation.value = createOfficeDelivery(template.format,filenamePreview.value,()=>mapping
    ? exportGenericForm(mapping,template,confirmedValues,stem)
    : buildForm(template,confirmedValues,image,stem,demo))
}

function togglePreview() {
  preview.value = !preview.value
  confirmation.value = undefined
}

async function deliver(destination:'download'|'vault') {
  const output = confirmation.value
  if (!output || !ready.value || saving.value || exporting.value || count.value || filenameError.value ||
      intake.value?.exportBlocked ||
      (props.fromNotice ? !intake.value : account.signedIn)) return
  const selection = intake.value
  const template = scenario.value
  const version = formVersion
  const accountId = account.user?.id
  const archive = destination==='vault'
  if (archive && (!props.savedBatchId || !selection || !accountId ||
      !vaultConsent.value || archivedFile.value || archiveUncertain.value)) return
  const caseId = vaultLinkCase.value ? selection?.caseId || undefined : undefined
  const sources = Object.values(profileFields.value)
  const awards = awardUses.value
  const reasonAwardsUsed = acceptedReason.value?.awards ?? []
  const stillConfirmed = ()=>mounted && version===formVersion && account.user?.id===accountId &&
    intake.value===selection && confirmation.value===output
  exporting.value = true
  problem.value = ''
  message.value = ''
  let checkingSources = false
  try {
    const archiveOutput = archive ? await output() : undefined
    if (!stillConfirmed()) return
    const save = archiveOutput ? await prepareVaultFormArchive(archiveOutput,caseId,vaultConsent.value,()=>
      stillConfirmed() && window.confirm('此 Office 文件没有完成端侧扫描。请确认已人工核对整个文件，允许上传到当前账号的材料库。')) : undefined
    if (!stillConfirmed() || (archive && !save)) return
    checkingSources = true
    if (selection?.verifyExport) {
      await selection.verifyExport()
      if (!stillConfirmed()) return
    }
    if ((sources.length || awards.length || reasonAwardsUsed.length) && accountId) {
      const [workspace,entries] = await Promise.all([
        sources.length ? loadWorkspace(accountId) : undefined,
        awards.length || reasonAwardsUsed.length ? loadExperiences(accountId) : [],
      ])
      if (!stillConfirmed()) return
      if (workspace) {
        const current = reviewAccountProfile(workspace,template,selection?.caseId || '',{})
        const stale = staleProfileLabels(sources,current.candidates)
        if (stale.length) throw Error('已从画像带入的字段需要重新核对（'+stale.join('、')+'）。请清除相关带入值后重新带入，也可手工填写。')
      }
      const available = awardCandidates(entries)
      if (reasonAwardsUsed.some(use=>{
        const entry = currentAward(use.entry,available)
        return !entry || entry.title!==use.entry.title || experienceSource(entry).quote!==use.source.quote
      })) throw Error('申请理由引用的奖项已变化。请核对后重新起草，或修改并确认手写理由。')
      const stale = [...new Set(awards.filter(use=>!currentAward(use.entry,available)).map(use=>use.entry.title))]
      if (stale.length) throw Error('已带入奖项需要重新核对（'+stale.join('、')+'）。请清除旧带入值后重新带入，也可手工填写。')
    }
    checkingSources = false
    const result = archiveOutput ?? await output()
    if (!stillConfirmed()) return
    verifiedFile.value = {filename:result.filename,bytes:result.blob.size}
    if (save) {
      const item = await save()
      if (stillConfirmed()) {
        archivedFile.value = item
        message.value = item.linkedCase ? '已存入材料库并关联当前事项。' : '已存入当前账号的材料库。'
      }
      return
    }
    const url = URL.createObjectURL(result.blob)
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    try { link.click() } catch (error) {
      URL.revokeObjectURL(url)
      throw error
    }
    if (selection) attachmentProgress.value[selection.progressId ?? selection.id] = 'exported'
    window.setTimeout(()=>URL.revokeObjectURL(url),15_000)
    message.value = '已发起文件下载。'
  } catch (error) {
    if (stillConfirmed()) {
      if (checkingSources && selection?.verifyExport) confirmation.value = undefined
      if (error instanceof VaultArchiveUncertain) archiveUncertain.value = true
      problem.value = error instanceof Error && !error.message.startsWith('无法连接在线服务')
        ? error.message : '复核或导出失败，请检查网络后重试。'
    }
  } finally {
    exporting.value = false
  }
}

function displayed(value: string, sensitive?: boolean) {
  return !value ? '待补充' : sensitive && !reveal.value ? '•••• '+value.slice(-4) : value
}
</script>

<template>
  <main class="form-demo">
    <header class="intro">
      <RouterLink :to="savedBatchId?`/imports/${savedBatchId}/sources`:fromNotice?'/imports/new':'/me'">{{ fromNotice?'← 返回导入通知':'← 返回我的' }}</RouterLink>
      <p class="eyebrow">有绪 CampusWeave · {{ fromNotice?'本机处理':'离线演示' }}</p>
      <h1>{{ fromNotice?'按通知填写附件':'智能填表' }}</h1>
      <RouterLink v-if="!fromNotice" to="/imports/new">导入自己的通知和附件</RouterLink>
      <p>{{ fromNotice?'先核对通知要求与申请表版本，再补齐资料并导出可编辑原格式文件。':'选择真实校园事务样例，补齐字段、预览并下载可编辑文件。请使用合成资料和图片。' }}</p>
    </header>

    <section v-if="savedBatchId && !account.signedIn" class="panel">
      <p>登录后可读取当前账户的已保存通知。</p>
      <RouterLink :to="{path:'/auth/login',query:{formBatch:savedBatchId}}">登录后继续填表</RouterLink>
    </section>
    <section v-else-if="account.signedIn && !fromNotice" class="panel">
      <p>这组样本仅在离线演示身份下开放。可从「我的」返回演示模式。</p>
    </section>

    <template v-else>
      <SavedNoticeIntake v-if="savedBatchId" :key="'saved:'+intakeKey" :batch-id="savedBatchId"
        :busy="!ready || saving || exporting || draftBusy" :progress="attachmentProgress" @invalidate="invalidateIntake" @accept="acceptIntake"/>
      <NoticeIntake v-else-if="fromNotice" :key="intakeKey" :busy="!ready || saving" :progress="attachmentProgress" @invalidate="invalidateIntake" @accept="acceptIntake"/>
      <details v-if="fromNotice && persistAllowed" class="panel">
        <summary>此浏览器的本机资料</summary>
        <p>只在选择保存补录时保存可复用字段，供此浏览器下次填写。</p>
        <button type="button" :disabled="saving || !ready" @click="clearRemembered">清除此浏览器保存的填表资料</button>
      </details>
      <section v-if="!fromNotice" class="panel">
        <label class="field">演示资料身份
          <select :value="owner" :disabled="saving || !ready" @change="switchOwner(($event.target as HTMLSelectElement).value as DemoOwner)">
            <option value="demo:forms">本机演示身份</option>
            <option value="demo:empty">独立空资料测试身份</option>
          </select>
        </label>
        <p>按身份分开保存。合成样例需主动加载。</p>
      </section>
      <nav v-if="!fromNotice" class="scenarios" aria-label="演示场景">
        <button v-for="item in scenarios" :key="item.id" type="button" :aria-pressed="scenario.id===item.id" :disabled="!ready || saving" @click="select(item)">
          <strong>{{ item.title }}</strong><small>{{ item.format.toUpperCase() }}</small>
        </button>
      </nav>

      <p v-if="savedBatchId && !intake?.draftKey && draftError" role="alert">{{ draftError }}</p>
      <template v-if="!fromNotice || intake">
      <section class="panel" aria-label="模板来源">
        <h2>{{ scenario.title }}</h2>
        <p>{{ scenario.provenance }}<template v-if="scenario.source"> ·
          <a :href="scenario.source" target="_blank" rel="noopener noreferrer">{{ scenario.school }}</a>
        </template></p>
        <p v-if="intake">已选原件：{{ intake.attachment }}。</p>
        <p v-if="intake?.exportBlocked" class="warning">{{ intake.exportBlocked }}</p>
        <p v-if="fromNotice && !persistAllowed">本次补录按当前文件管理。</p>
        <p v-if="intake?.genericMapping">此原表的填写值仅保留在当前页面，需逐项核对未识别区和人工办理项。</p>
        <details v-if="intake?.genericMapping?.form.manual.length">
          <summary>查看原表保留区域</summary>
          <ul><li v-for="(item,index) in intake.genericMapping.form.manual" :key="index">{{ item.where }} · {{ item.text }}</li></ul>
        </details>
        <div v-if="!fromNotice" class="actions">
          <button type="button"  :disabled="!ready || saving" @click="fillExamples">用合成资料补齐缺项</button>
          <button type="button"  :disabled="!ready || saving" @click="clearRemembered">清除本机演示资料</button>
        </div>
      </section>

      <section v-if="savedBatchId && intake?.draftKey" class="panel" aria-label="原件草稿">
        <h2>保存原件草稿</h2>
        <p>主动保存后保留 {{ draftRetentionDays }} 天。同一账号可在此设备重新登录续填。主动退出会清除此账号在此设备的全部草稿。</p>
        <p v-if="draftFields.length">可保存的手填字段 · {{ draftFields.map(field=>field.label).join('、') }}。续填时可重新带入画像。证件号、联系方式、理由、照片和导出确认仅用于当前填写。</p>
        <p v-else>这份表暂无可保存的字段。</p>
        <p v-if="draftExpiryLabel">当前草稿保存至 {{ draftExpiryLabel }}。</p>
        <div class="actions">
          <button type="button" :disabled="exporting || draftBusy || account.formDraftEpoch===null || !draftFields.length" @click="saveDraftProgress">保存当前草稿</button>
          <button v-if="draftConflict" type="button" :disabled="exporting || draftBusy" @click="reopenSavedProgress">读取已保存的版本</button>
          <button v-if="savedDrafts.length" type="button" :disabled="exporting || draftBusy" @click="clearDraftProgress">清除本批次保存的草稿</button>
        </div>
        <p v-if="draftMessage" role="status">{{ draftMessage }}</p>
        <p v-if="draftError" role="alert">{{ draftError }}</p>
      </section>

      <details v-if="priorDrafts.length" class="panel">
        <summary>对照已移除或改版的草稿</summary>
        <label class="field">旧草稿
          <select v-model="priorDraftKey" :disabled="exporting" @change="carriedFields=[]">
            <option value="">选择旧草稿</option>
            <option v-for="item in priorDrafts" :key="item.key" :value="item.key">{{ item.name }}</option>
          </select>
        </label>
        <p>仅带入勾选的字段。文件名、照片和先前的导出确认需重新核对。</p>
        <label v-for="field in comparableFields" :key="field.id" class="toggle">
          <input v-model="carriedFields" type="checkbox" :value="field.id" :disabled="exporting">
          {{ field.label }} · {{ displayed(priorValues[field.id],field.sensitive) }}
        </label>
        <details v-if="priorReason">
          <summary>查看旧理由（仅供对照）</summary>
          <p class="reason-snapshot">{{ priorReason }}</p>
        </details>
        <button type="button" :disabled="!carriedFields.length || exporting" @click="carryPreviousFields">带入选中的旧值</button>
      </details>

      <details v-if="!fromNotice" class="panel">
        <summary>手上只有赛事通知？</summary>
        <label class="field">粘贴公开通知片段
          <textarea v-model="notice" rows="3" maxlength="3000" placeholder="例如：校园竞赛材料提交截止时间为……"></textarea>
        </label>
        <p v-if="competition" role="status">这段通知可能涉及赛事报名或材料提交，可到日程安排跟进截止时间。</p>
        <RouterLink v-if="competition" to="/plan/schedule">转到日程安排</RouterLink>
      </details>

      <section class="panel" aria-label="填写表单">
        <div class="section-head">
          <h2>{{ showAll ? '编辑整张表单' : '补录所需资料' }}</h2>
          <p aria-live="polite">{{ count ? count+' 项待补充或修正' : intake?.genericMapping ? '已识别字段已填写，请核对原件其余区域' : '申请人字段已齐全' }}</p>
        </div>
        <div class="actions">
          <button type="button" @click="showAll=!showAll">{{ showAll ? '只显示补录字段' : '显示并编辑整张表单' }}</button>
        </div>
        <AccountProfileFill v-if="savedBatchId && intake && !intake.genericMapping && account.signedIn" :key="intake.id"
          :scenario="scenario" :case-id="intake.caseId" :values="values" :disabled="saving || exporting"
          @apply="fillFromAccountProfile"/>
        <button v-if="Object.keys(profileFields).length" type="button" :disabled="exporting" @click="clearProfileFields">
          清除画像带入值
        </button>
        <AccountAwardFill v-if="savedBatchId && intake && account.signedIn && scenario.id==='scholarship'"
          :key="intake.id" :values="values" :disabled="saving || exporting" @apply="fillFromAccountAward"/>
        <button v-if="awardUses.length" type="button" :disabled="exporting" @click="clearAwardFields">清除奖项带入值</button>
        <p v-if="!groups.length">本次没有资料缺项。可预览，或打开整表修改。</p>
        <fieldset v-for="group in groups" :key="group.title" :disabled="saving || !ready || exporting">
          <legend>{{ group.title }}</legend>
          <div class="fields">
            <div v-for="field in group.fields" :key="field.id" class="field" :class="{wide:field.type==='long'}">
              <label :for="field.id">{{ field.label }} <small v-if="field.optional">选填</small></label>
              <select v-if="field.choices" :id="field.id" v-model="values[field.id]" :aria-invalid="Boolean(review.errors[field.id])" @change="changed">
                <option value="">请选择</option>
                <option v-for="choice in field.choices" :key="choice">{{ choice }}</option>
              </select>
              <textarea v-else-if="field.type==='long'" :id="field.id" v-model="values[field.id]" rows="4" :aria-invalid="Boolean(review.errors[field.id])" @input="changed"></textarea>
              <input v-else :id="field.id" v-model="values[field.id]" :type="field.type==='date'?'date':field.sensitive&&!reveal?'password':'text'"
                :inputmode="field.type==='number'?'numeric':undefined" :aria-invalid="Boolean(review.errors[field.id])" autocomplete="off" @input="changed">
              <small v-if="field.hint">{{ field.hint }}</small>
              <small v-if="review.errors[field.id]" class="warning">{{ review.errors[field.id] }}</small>
              <details v-if="profileFields[field.id]">
                <summary>已从个人画像带入</summary>
                <small v-for="source in profileFields[field.id].refs" :key="source.id">{{ source.quote }} · {{ source.id }}<br></small>
              </details>
              <details v-if="awardSources[field.id]">
                <summary>已从本机经历带入</summary>
                <small>{{ awardSources[field.id].quote }} · 版本 {{ awardSources[field.id].revision }} · {{ awardSources[field.id].id }}</small>
              </details>
              <template v-if="field.id==='reason' && acceptedReason">
                <details>
                  <summary>{{ values.reason===acceptedReason.text?'查看已采用的本机稿':'查看修改前的本机稿' }}</summary>
                  <p class="reason-snapshot">{{ acceptedReason.text }}</p>
                  <small v-for="item in acceptedReason.awards" :key="item.source.id">
                    {{ item.source.quote }} · 版本 {{ item.source.revision }} · {{ item.source.id }}<br>
                  </small>
                </details>
                <button v-if="acceptedReason.awards.length && values.reason!==acceptedReason.text" type="button"
                  :disabled="exporting" @click="confirmManualReason">确认手写理由的事实并解除档案引用</button>
              </template>
              <small>{{ intake?.draftKey && draftFields.includes(field) ? '可随原件草稿保存' : persistAllowed && profileKey(scenario,field) ? '保存补录后可在适用场景复用' : '仅用于本次表单' }}</small>
            </div>
          </div>
        </fieldset>
        <ApplicationReasonDraft v-if="fromNotice && intake" :key="reasonEditorKey"
          :scenario="scenario" :awards="reasonSources" :value="values.reason || ''"
          :disabled="saving || !ready || exporting" @apply="acceptReason"/>
        <section v-if="scenario.id==='scholarship' && (!fromNotice || persistAllowed)" class="award-archive" aria-label="演示经历档案">
          <h3>演示经历档案</h3>
          <p>保存已填的获奖组，下次可以填入空白奖项。填表时仍需核对年月、顺序和申报范围。</p>
          <div class="actions">
            <button v-for="slot in awardSlots" :key="slot" type="button" :disabled="!readAward(values,slot)" @click="storeAward(slot)">保存获奖组 {{ slot }}</button>
          </div>
          <ul v-if="archive.length">
            <li v-for="(award,index) in archive" :key="index">{{ award.date }} · {{ award.name }}
              <button type="button" class="text-button" :disabled="!nextAwardSlot(values)" @click="applyAward(award)">填入空白奖项</button>
            </li>
          </ul>
          <button v-if="!fromNotice" type="button" @click="suggestReason">起草申请理由</button>
          <div v-if="!fromNotice && reasonSuggestion">
            <p>{{ reasonSuggestion }}</p>
            <button type="button" @click="useReason">使用这份理由</button>
          </div>
        </section>
        <p v-if="scenario.id==='leave' && days>0">请假 {{ days }} 天，含起止当日。</p>
        <ul v-if="review.reminders.length"><li v-for="reminder in review.reminders" :key="reminder">{{ reminder }} <a :href="scenario.source" target="_blank" rel="noopener noreferrer">校方依据</a></li></ul>

        <p v-if="scenario.photo==='physical'" class="warning">
          {{ scenario.photoNote || '照片需打印后粘贴。导出保留照片框。' }}
          <a v-if="scenario.source" :href="scenario.source" target="_blank" rel="noopener noreferrer">校方依据</a>
        </p>
        <fieldset v-if="scenario.photo==='embedded'" :disabled="saving">
          <legend>演示照片</legend>
          <div class="photo-panel">
            <img v-if="photo" :src="photo" alt="将嵌入表格的演示照片">
            <div>
              <p v-if="review.errors.photo" class="warning">{{ review.errors.photo }}</p>
              <button type="button" @click="useAvatar">使用合成照片</button>
              <label class="field">选择合成 PNG / JPEG<input type="file" accept="image/png,image/jpeg" @change="choosePhoto"></label>
              <template v-if="photoInput">
                <label class="field">缩放<input v-model.number="zoom" type="range" min="1" max="2" step=".1" @input="cropPhoto"></label>
                <label class="field">上下位置<input v-model.number="vertical" type="range" min="0" max="100" @input="cropPhoto"></label>
              </template>
            </div>
          </div>
        </fieldset>

        <label class="toggle"><input v-model="reveal" type="checkbox"> 显示敏感字段原值</label>
        <label class="field">文件名（不含扩展名）
          <input :placeholder="suggestedStem" :value="nameOverride" :disabled="exporting" @input="nameOverride=($event.target as HTMLInputElement).value; changed()">
        </label>
        <p class="file-name">{{ filenamePreview }}</p>
        <p v-if="filenameError" class="warning">{{ filenameError }}</p>
        <div class="actions">
          <button type="button" class="primary" :disabled="Boolean(count) || saving || !ready" @click="saveCompletion">{{ persistAllowed?'保存补录并预览':'确认补录并预览' }}</button>
          <button type="button" :disabled="!ready || saving" @click="togglePreview">{{ preview?'收起字段预览':'预览填写内容' }}</button>
        </div>
      </section>

      <section v-if="preview" class="panel" aria-label="导出预览">
        <h2>导出内容预览</h2>
        <dl v-for="group in scenario.groups" :key="group.title" class="preview-values">
          <template v-for="field in group.fields" :key="field.id">
            <dt>{{ field.label }}</dt><dd>{{ displayed(values[field.id],field.sensitive) }}</dd>
          </template>
        </dl>
        <img v-if="scenario.photo==='embedded' && photo" class="preview-photo" :src="photo" alt="导出照片预览">
        <section class="delivery-review" aria-label="版式与交付检查">
          <h3>导出文件</h3>
          <p class="file-name">{{ filenamePreview }}</p>
          <p v-if="fromNotice">下载后请按通知自行提交文件。</p>
          <p>请在 {{ scenario.format==='xlsx' ? 'Excel 或 WPS 表格' : 'Word 或 WPS 文字' }} 中核对版式。需要纸质件时，请先检查打印预览。</p>
          <p v-if="scenario.printNote" class="warning">{{ scenario.printNote }}</p>
          <p>人工办理 · {{ scenario.manual }}</p>
          <p v-if="scenario.photo==='physical'">照片框留空。打印后请按原件及适用通知粘贴照片。</p>
          <details v-if="handoffRequests.length">
            <summary>核对通知中的办理要求</summary>
            <ul>
              <li v-for="item in handoffRequests" :key="item.id">正文第 {{ item.line }} 行 · {{ item.text }}</li>
            </ul>
          </details>
          <p v-if="(intake?.manualReviews || 0)>handoffRequests.filter(item=>item.kind==='review').length">其他要求请查看上方通知依据。</p>
          <details v-if="intake?.genericMapping?.form.manual.length">
            <summary>核对原表说明和保留区域</summary>
            <ul>
              <li v-for="(item,index) in intake.genericMapping.form.manual" :key="index">{{ item.where }} · {{ item.text }}</li>
            </ul>
          </details>
        </section>
        <label class="toggle"><input type="checkbox" :checked="Boolean(confirmation)" :disabled="Boolean(count || filenameError || intake?.exportBlocked) || !ready || saving || exporting" @change="confirmOutput"> 我确认这份文件的填写值和文件名<span v-if="scenario.id==='leave'">，并已核对起止节次及总节数</span></label>
        <button type="button" class="primary" :disabled="!confirmation || Boolean(count || filenameError || intake?.exportBlocked) || !ready || saving || exporting" @click="deliver('download')">确认并下载 {{ scenario.format.toUpperCase() }}</button>
        <p v-if="verifiedFile" role="status">文件校验通过 · {{ verifiedFile.filename }} · {{ verifiedFile.bytes }} 字节</p>
        <details v-if="savedBatchId && account.signedIn && confirmation && !intake?.exportBlocked" class="vault-archive">
          <summary>保存到材料库</summary>
          <template v-if="archivedFile || archiveUncertain">
            <p v-if="archivedFile">此确认版本已保存{{ archivedFile.linkedCase ? '并关联当前事项' : '' }}。</p>
            <p v-else>保存状态待核对。</p>
            <RouterLink to="/vault">查看材料库</RouterLink>
          </template>
          <template v-else>
            <p>将当前确认的 {{ filenamePreview }} 上传并保存在你的账号中。</p>
            <label v-if="intake?.caseId" class="toggle">
              <input v-model="vaultLinkCase" type="checkbox" :disabled="exporting"> 关联此通知的事项
            </label>
            <label class="toggle">
              <input v-model="vaultConsent" type="checkbox" :disabled="exporting">
              我已核对文件隐私并同意上传到当前账号的材料库
            </label>
            <button type="button" :disabled="!vaultConsent || saving || exporting" @click="deliver('vault')">上传并存入材料库</button>
          </template>
        </details>
        <details v-if="intake?.genericMapping">
          <summary>查看填写清单</summary>
          <ul>
            <li v-for="item in mappedFields(intake.genericMapping)" :key="item.field.id">
              {{ item.field.label }} · {{ displayed(values[item.field.id],item.field.sensitive) }}
            </li>
          </ul>
        </details>
        <p v-if="exporting && savedBatchId" role="status">正在复核来源、通知要求及原件…</p>
      </section>
      </template>
      <p v-if="message" role="status" class="feedback">{{ message }}</p>
      <p v-if="problem" role="alert" class="feedback warning">{{ problem }}</p>
    </template>
  </main>
</template>

<style scoped>
.form-demo{max-width:880px;margin:0 auto;padding:1rem 1rem 6rem;color:#18243a}
.intro,.panel{margin-bottom:1rem}
.intro h1{margin:.2rem 0;font-size:2rem}
.eyebrow{margin-bottom:0;color:#28579b;font-weight:700}
.panel{background:white;border:1px solid #dce5f0;border-radius:1rem;padding:1rem}
.panel h2{margin:.1rem 0 .5rem;font-size:1.22rem}
.panel p{line-height:1.55}
.scenarios,.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
.scenarios{margin-bottom:1rem}
button{border:1px solid #c6d5e8;background:#eef5ff;color:#1a4782;border-radius:.55rem;padding:.55rem .7rem;font:inherit;text-align:left;cursor:pointer}
button[aria-pressed="true"],button.primary{background:#1b4e91;color:white;border-color:#1b4e91}
button:disabled{opacity:.55;cursor:default}
.scenarios small{display:block;margin-top:.2rem}
.actions,.section-head,.photo-panel{display:flex;gap:.65rem;align-items:flex-start;flex-wrap:wrap}
.section-head{justify-content:space-between}
fieldset{min-width:0;border:1px solid #e0e7f0;border-radius:.65rem;padding:.65rem;margin:0 0 .7rem}
.delivery-review{margin:1rem 0;padding:.7rem;border:1px solid #e0e7f0;border-radius:.65rem}
.delivery-review h3{margin:0 0 .6rem}
.vault-archive{margin:1rem 0}
legend{font-weight:700;padding:0 .2rem}
.field{display:grid;gap:.2rem;margin:.2rem 0;font-size:.92rem;min-width:0}
.field input,.field select,.field textarea{box-sizing:border-box;width:100%;min-height:2.4rem;border:1px solid #bacce2;border-radius:.45rem;padding:.45rem;background:white;color:#18243a;font:inherit}
.wide{grid-column:1/-1}
.warning{color:#9b351f}
.text-button{border:0;background:transparent;padding:.2rem 0;font-size:.85rem;justify-self:start}
.toggle{display:flex;gap:.5rem;align-items:center;margin:.75rem 0}
.preview-values{display:grid;grid-template-columns:minmax(6rem,1fr) 2fr;border-bottom:1px solid #e0e7f0;gap:.35rem}
.preview-values dt{font-weight:600}
.preview-values dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
.photo-panel img,.preview-photo{width:90px;aspect-ratio:5/7;object-fit:cover;border:1px solid #dce5f0}
.award-archive{border:1px solid #e0e7f0;border-radius:.65rem;padding:.65rem;margin-bottom:.8rem}
.award-archive h3{margin:.15rem 0;font-size:1rem}
.reason-snapshot{white-space:pre-wrap;overflow-wrap:anywhere}
.file-name{overflow-wrap:anywhere}
.feedback{position:sticky;bottom:4rem;padding:.65rem;border-radius:.5rem;background:#eef5ff}
@media(max-width:480px){.fields{grid-template-columns:1fr}.form-demo{padding-inline:.7rem}}
</style>
