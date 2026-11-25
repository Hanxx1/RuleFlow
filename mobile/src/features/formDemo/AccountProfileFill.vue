<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {useAccountStore} from '../../stores/account'
import {loadWorkspace} from '../../services/clientWorkspace'
import {applyProfileCandidates,reviewAccountProfile,type ProfileCandidate} from './accountFormProfile'
import type {FormValues,Scenario} from './scenarios'

const props = defineProps<{scenario:Scenario;caseId?:string|null;values:FormValues;disabled:boolean}>()
const emit = defineEmits<{apply:[candidates:ProfileCandidate[]]}>()
const account = useAccountStore()
const review = ref<ReturnType<typeof reviewAccountProfile>>()
const selected = ref<string[]>([])
const error = ref('')
const busy = ref(false)
let read = 0
const available = computed(()=>review.value?.candidates.filter(item=>!props.values[item.id]?.trim()) || [])

function setReview(next: ReturnType<typeof reviewAccountProfile>) {
  review.value = next
  selected.value = next.candidates.map(item=>item.id)
}

async function load(apply: boolean) {
  const owner = account.user?.id
  if (!owner || props.disabled || busy.value) return
  const previous = review.value
  const requested = [...selected.value]
  const id = ++read
  busy.value = true
  error.value = ''
  try {
    const workspace = await loadWorkspace(owner)
    if (id!==read || account.user?.id!==owner) return
    const next = reviewAccountProfile(workspace,props.scenario,props.caseId || '',props.values)
    if (!apply || !previous) {
      setReview(next)
      return
    }
    const stillEmpty = applyProfileCandidates(props.values,previous.candidates,requested)
    const actual = applyProfileCandidates(props.values,next.candidates,requested)
    if (previous.revision!==next.revision || JSON.stringify(stillEmpty)!==JSON.stringify(actual)) {
      setReview(next)
      error.value = '画像已更新，请按当前资料重新核对。'
      return
    }
    emit('apply',actual)
    review.value = undefined
    selected.value = []
  } catch {
    if (id===read) {
      error.value = '无法读取此账号的本机画像，可以继续手工填写。'
      review.value = undefined
      selected.value = []
    }
  } finally {
    if (id===read) busy.value = false
  }
}

function reset() {
  read++
  review.value = undefined
  selected.value = []
  busy.value = false
  error.value = ''
}
watch([()=>account.user?.id,()=>props.scenario.id,()=>props.caseId],reset)
onBeforeUnmount(()=>{read++})
</script>

<template>
  <section class="profile-fill" aria-label="账户画像补录">
    <h3>从个人画像补录</h3>
    <button type="button" :disabled="disabled || busy" @click="load(false)">
      {{ busy ? '正在核对本机画像…' : '核对可带入的画像字段' }}
    </button>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="review">
      <p v-if="review.issue" role="status">{{ review.issue }}</p>
      <template v-else>
        <p v-if="review.skipped.length">需手工核对 · {{ review.skipped.join('、') }}。仅使用已确认、未过期且无冲突的值。</p>
        <p v-if="!available.length" role="status">本表当前没有可从画像补入的空项。</p>
        <ul v-else>
          <li v-for="item in available" :key="item.id">
            <label><input v-model="selected" type="checkbox" :value="item.id" :disabled="disabled || busy">
              {{ item.label }} · {{ item.value }}
            </label>
            <details>
              <summary>查看已确认的画像依据</summary>
              <ul>
                <li v-for="source in item.refs" :key="source.id">
                  {{ source.quote }}<template v-if="source.validUntil"> · 有效至 {{ source.validUntil }}</template>
                  <small> · {{ source.id }}</small>
                </li>
              </ul>
            </details>
          </li>
        </ul>
        <button v-if="available.length" type="button" :disabled="disabled || busy || !available.some(item=>selected.includes(item.id))"
          @click="load(true)">带入选中的空项</button>
      </template>
    </template>
  </section>
</template>

<style scoped>
.profile-fill{border:1px solid #e0e7f0;border-radius:.7rem;padding:.7rem;margin-bottom:1rem}
.profile-fill h3{margin:0 0 .5rem}
.profile-fill li{overflow-wrap:anywhere}
.profile-fill button{border:1px solid #c6d5e8;background:#eef5ff;color:#1a4782;border-radius:.55rem;padding:.55rem .7rem;font:inherit}
.profile-fill button:disabled{opacity:.55}
</style>
