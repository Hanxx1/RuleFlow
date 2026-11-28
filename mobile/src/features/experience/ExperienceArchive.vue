<script setup lang="ts">
import {onBeforeUnmount,ref,watch} from 'vue'
import {useAccountStore} from '../../stores/account'
import {changeExperience,emptyExperience,experienceKinds,experienceLimits,experienceSource,loadExperiences,
  type Experience,type ExperienceChange} from './archive'

const account = useAccountStore()
const records = ref<Experience[]>([])
const form = ref(emptyExperience())
const editing = ref<Pick<Experience,'id'|'revision'>>()
const pending = ref(false)
const loaded = ref(false)
const feedback = ref('')
const error = ref('')
let request = 0

function resetEditor(entry?:Experience) {
  editing.value = entry && {id:entry.id,revision:entry.revision}
  form.value = entry ? {...entry} : emptyExperience()
  feedback.value = ''
  error.value = ''
}

async function reload() {
  const owner = account.user?.id
  const token = ++request
  records.value = []
  loaded.value = false
  resetEditor()
  pending.value = Boolean(owner)
  if (!owner) return
  try {
    const next = await loadExperiences(owner)
    if (account.user?.id!==owner || token!==request) return
    records.value = next
    loaded.value = true
  } catch {
    if (token===request) error.value = '无法读取此账号的本机经历。'
  } finally {
    if (token===request) pending.value = false
  }
}

async function commit(change:ExperienceChange,notice:string) {
  const owner = account.user?.id
  if (!owner || pending.value || !loaded.value) return
  const token = ++request
  const current = ()=>account.user?.id===owner && token===request
  pending.value = true
  feedback.value = ''
  error.value = ''
  try {
    const next = await changeExperience(owner,change,current)
    if (!current()) return
    records.value = next
    if (!('remove' in change) || editing.value?.id===change.id) resetEditor()
    feedback.value = notice
  } catch (failure) {
    if (current()) error.value = failure instanceof Error ? failure.message : '本机经历保存失败。'
  } finally {
    if (current()) pending.value = false
  }
}

function save(confirmed:boolean) {
  const key = editing.value ?? {id:crypto.randomUUID(),revision:0}
  void commit({...key,input:{...form.value},confirmed},confirmed?'已确认此经历。':'已保存为待确认。')
}

function remove(entry:Experience) {
  if (!window.confirm('删除这条本机经历？已下载的文件会保留原值，请核对后提交。')) return
  void commit({id:entry.id,revision:entry.revision,remove:true},'已删除此经历。')
}

watch(()=>account.user?.id,reload,{immediate:true})
onBeforeUnmount(()=>{request++})
</script>

<template>
  <section class="surface-card experience" aria-label="本机经历档案">
    <h2>本机经历档案</h2>
    <p>此账号的档案保存在当前设备。确认后可供适用的表单使用。退出账号会清除，当前本机备份暂未包含经历。</p>
    <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
    <p v-if="feedback" role="status">{{ feedback }}</p>
    <button type="button" class="button button--secondary" :disabled="pending" @click="reload">重新读取经历</button>
    <p v-if="loaded && !records.length">还没有经历记录。</p>
    <ul v-if="records.length" class="entries">
      <li v-for="entry in records" :key="entry.id">
        <strong>{{ entry.title }}</strong> · {{ experienceKinds[entry.kind] }} ·
        {{ entry.month }}{{ entry.endMonth ? ' 至 '+entry.endMonth : '' }} · {{ entry.confirmed?'已确认':'待确认' }}
        <p v-if="entry.issuer">{{ entry.issuer }}{{ entry.level ? ' · '+entry.level : '' }}</p>
        <details v-if="entry.confirmed">
          <summary>查看用户确认的来源</summary>
          <small>{{ experienceSource(entry).quote }} · 版本 {{ entry.revision }}</small>
        </details>
        <div class="button-row">
          <button type="button" class="button button--secondary" :disabled="pending" @click="resetEditor(entry)">编辑与核对</button>
          <button type="button" class="button button--secondary" :disabled="pending" @click="remove(entry)">删除经历</button>
        </div>
      </li>
    </ul>
    <form v-if="loaded" class="form-card" @submit.prevent="save(false)">
      <h3>{{ editing?'编辑经历':'新增经历' }}</h3>
      <fieldset :disabled="pending">
        <label>经历类型<select v-model="form.kind">
          <option v-for="(title,kind) in experienceKinds" :key="kind" :value="kind">{{ title }}</option>
        </select></label>
        <label>经历名称<input v-model="form.title" :maxlength="experienceLimits.title"></label>
        <label>{{ form.kind==='award'?'获奖年月':'开始年月' }}<input v-model="form.month" type="month" placeholder="YYYY-MM"></label>
        <label v-if="form.kind!=='award'">结束年月（选填）<input v-model="form.endMonth" type="month" placeholder="YYYY-MM"></label>
        <label>{{ form.kind==='award'?'颁奖单位':'举办单位（选填）' }}<input v-model="form.issuer" :maxlength="experienceLimits.issuer"></label>
        <label>级别（选填）<input v-model="form.level" :maxlength="experienceLimits.level"></label>
        <details>
          <summary>填写角色、成果和证明备注</summary>
          <label>角色（选填）<input v-model="form.role" :maxlength="experienceLimits.role"></label>
          <label>贡献（选填）<textarea v-model="form.contribution" :maxlength="experienceLimits.contribution" rows="2"></textarea></label>
          <label>成果（选填）<textarea v-model="form.result" :maxlength="experienceLimits.result" rows="2"></textarea></label>
          <label>时长（选填，单位为小时）<input v-model="form.hours" inputmode="decimal" :maxlength="experienceLimits.hours"></label>
          <label>证明备注（选填）<input v-model="form.proofNote" :maxlength="experienceLimits.proofNote"></label>
          <small>可记下证明名称或保管位置，供自己核对。</small>
        </details>
        <div class="button-row">
          <button type="submit" class="button button--secondary">保存为待确认</button>
          <button type="button" class="button button--primary" @click="save(true)">确认并保存经历</button>
          <button v-if="editing" type="button" class="button button--secondary" @click="resetEditor()">取消编辑</button>
        </div>
      </fieldset>
    </form>
  </section>
</template>

<style scoped>
.experience fieldset{display:grid;gap:.6rem;border:0;margin:0;padding:0;min-width:0}
.experience label{display:grid;gap:.25rem;margin:.35rem 0}
.experience .entries{padding-left:1.2rem;overflow-wrap:anywhere}
.experience .entries li{margin:.8rem 0}
</style>
