<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {useAccountStore} from '../../stores/account'
import {experienceSource,loadExperiences,type Experience} from '../experience/archive'
import {awardCandidates,currentAward,planAward,type AwardUse} from './accountAwardFill'
import type {FormValues} from './scenarios'

const props = defineProps<{values:FormValues;disabled:boolean}>()
const emit = defineEmits<{apply:[use:AwardUse]}>()
const account = useAccountStore()
const entries = ref<Experience[]>()
const busy = ref(false)
const error = ref('')
let request = 0
const options = computed(()=>entries.value?.map(entry=>({entry,plan:planAward(entry,props.values)})))

async function review(selected?:Experience) {
  const owner = account.user?.id
  if (!owner || busy.value || props.disabled) return
  const token = ++request
  const current = ()=>request===token && account.user?.id===owner
  busy.value = true
  error.value = ''
  try {
    const available = awardCandidates(await loadExperiences(owner))
    if (!current()) return
    entries.value = available
    if (!selected || props.disabled) return
    const same = currentAward(selected,available)
    if (!same) {
      error.value = '此经历已修改、取消确认或删除，请按当前档案重新核对。'
      return
    }
    const plan = planAward(same,props.values)
    if (plan) emit('apply',plan)
    else error.value = '没有符合顺序的空白行，或同一奖项已填写。请核对获奖经历。'
  } catch {
    if (current()) {
      entries.value = undefined
      error.value = '无法读取本机经历，可以继续手工填写。'
    }
  } finally {
    if (current()) busy.value = false
  }
}

watch(()=>account.user?.id,()=>{
  request++
  entries.value = undefined
  busy.value = false
  error.value = ''
})
onBeforeUnmount(()=>{request++})
</script>

<template>
  <section class="award-fill" aria-label="从本机经历带入奖项">
    <h3>从本机经历带入奖项</h3>
    <p>请按通知核对申报范围。系统只列出已确认且符合原表年月、名称和单位格式的奖项。</p>
    <button type="button" :disabled="disabled || busy" @click="review()">核对可带入的奖项</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="options">
      <p v-if="!options.length" role="status">没有可用的已确认奖项。可在个人画像的本机经历档案添加，或直接手填。</p>
      <ul v-else>
        <li v-for="{entry,plan} in options" :key="entry.id">
          <strong>{{ entry.title }}</strong> · {{ entry.month }} · {{ entry.issuer }}
          <details>
            <summary>查看用户确认的来源</summary>
            <small>{{ experienceSource(entry).quote }} · 版本 {{ entry.revision }} · {{ experienceSource(entry).id }}</small>
          </details>
          <button type="button" :aria-label="'带入奖项 '+entry.title" :disabled="disabled || busy || !plan"
            @click="review(entry)">带入空白行</button>
          <small v-if="!plan">已填写此奖项，或没有符合年月顺序的空白行。</small>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.award-fill{border:1px solid #e0e7f0;border-radius:.7rem;padding:.7rem;margin-bottom:1rem}
.award-fill h3{margin:0 0 .5rem}
.award-fill li{overflow-wrap:anywhere;margin:.5rem 0}
.award-fill li>small{display:block}
</style>
