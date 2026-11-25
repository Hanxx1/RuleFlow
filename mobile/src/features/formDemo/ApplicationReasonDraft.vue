<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {useAccountStore} from '../../stores/account'
import {loadExperiences} from '../experience/archive'
import {awardCandidates,currentAward} from './accountAwardFill'
import {draftApplicationReason,reasonField,reasonLength,type ReasonAward,type ReasonVersion} from './reasonDraft'
import type {Scenario} from './scenarios'

const props = defineProps<{scenario:Scenario;awards:ReasonAward[];value:string;disabled:boolean}>()
const emit = defineEmits<{apply:[version:ReasonVersion]}>()
const account = useAccountStore()
const details = ref('')
const selected = ref<string[]>([])
const candidate = ref<{version:ReasonVersion;baseline:string}>()
const error = ref('')
const busy = ref(false)
const field = computed(()=>reasonField(props.scenario))
const count = computed(()=>reasonLength(candidate.value?.version.text ?? ''))
const reasonChanged = computed(()=>Boolean(candidate.value && candidate.value.baseline!==props.value))
const awardsChanged = computed(()=>candidate.value?.version.awards.some(award=>
  !props.awards.some(item=>item.entry.id===award.entry.id && item.entry.revision===award.entry.revision)))
let read = 0
onBeforeUnmount(()=>{read++})

function discard() {
  read++
  candidate.value = undefined
  busy.value = false
  error.value = ''
}

watch(()=>account.user?.id,()=>{
  discard()
  selected.value = []
  details.value = ''
})
watch([details,selected],discard)

function draft() {
  discard()
  const result = draftApplicationReason(props.scenario,details.value,
    props.awards.filter(item=>selected.value.includes(item.entry.id)))
  if (result.version) candidate.value = {version:result.version,baseline:props.value}
  else error.value = result.issue
}

async function apply() {
  const snapshot = candidate.value
  if (!snapshot || reasonChanged.value || awardsChanged.value || busy.value || props.disabled) return
  const owner = account.user?.id
  const token = ++read
  const current = ()=>token===read && owner===account.user?.id
  busy.value = true
  error.value = ''
  try {
    if (snapshot.version.awards.length) {
      const available = owner ? awardCandidates(await loadExperiences(owner)) : []
      if (!current()) return
      if (snapshot.version.awards.some(award=>!currentAward(award.entry,available))) {
        error.value = '引用的奖项已修改、取消确认或删除。请重新核对经历，或起草不引用奖项的理由。'
        return
      }
    }
    if (current() && !props.disabled && !reasonChanged.value && !awardsChanged.value) {
      emit('apply',snapshot.version)
      discard()
      details.value = ''
    }
  } catch {
    if (current()) error.value = '暂时无法复核本机经历。可手工填写，或起草不引用奖项的理由。'
  } finally {
    if (current()) busy.value = false
  }
}
</script>

<template>
  <details v-if="field" class="reason-draft">
    <summary>起草{{ field.label }}</summary>
    <fieldset :disabled="disabled || busy">
      <p v-if="field.min || field.max">{{ field.label }}字数要求
        {{ field.min ? '至少 '+field.min+' 字' : '' }}{{ field.min && field.max ? '，' : '' }}{{ field.max ? '最多 '+field.max+' 字' : '' }}。
      </p>
      <template v-if="scenario.id==='scholarship'">
        <p v-if="awards.length">可选择本表已带入的奖项作为理由依据。留空可起草通用稿。</p>
        <label v-for="award in awards" :key="award.entry.id" class="award-option">
          <input v-model="selected" type="checkbox" :value="award.entry.id">
          引用奖项 {{ award.entry.title }}
        </label>
      </template>
      <label v-else class="details-input">本次真实事由
        <textarea v-model="details" rows="3" maxlength="500" autocomplete="off"></textarea>
      </label>
      <button type="button" @click="draft">在本机起草</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <section v-if="candidate" aria-label="理由草稿预览">
        <p class="draft-text">{{ candidate.version.text }}</p>
        <p>{{ count }} 字</p>
        <ul v-if="candidate.version.awards.length">
          <li v-for="award in candidate.version.awards" :key="award.source.id">
            {{ award.source.quote }} · 版本 {{ award.source.revision }} · {{ award.source.id }}
          </li>
        </ul>
        <p v-if="reasonChanged || awardsChanged" role="status">原填写值或所选奖项已变化，请重新起草。</p>
        <div class="actions">
          <button type="button" :disabled="reasonChanged || awardsChanged" @click="apply">
            {{ value.trim() ? '用此稿替换当前理由' : '将此稿填入理由栏' }}
          </button>
          <button type="button" @click="discard">舍弃生成稿</button>
        </div>
      </section>
    </fieldset>
  </details>
</template>

<style scoped>
.reason-draft{border:1px solid #e0e7f0;border-radius:.65rem;margin-bottom:1rem;padding:.7rem;overflow-wrap:anywhere}
.reason-draft summary{cursor:pointer;font-weight:600}
.reason-draft fieldset{border:0;padding:0;margin:0;min-width:0}
.reason-draft .award-option,.reason-draft .details-input{display:block;margin:.65rem 0}
.reason-draft textarea{display:block;width:100%;box-sizing:border-box;margin-top:.3rem}
.reason-draft .draft-text{white-space:pre-wrap}
.reason-draft .actions{display:flex;flex-wrap:wrap;gap:.5rem}
</style>
