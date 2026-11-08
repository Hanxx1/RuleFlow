<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {useAccountStore} from '../../stores/account'
import {avatarUrl,buildForm} from './exportForm'
import {awardReason,awardSlots,nextAwardSlot,readAward,writeAward,type DemoAward} from './demoAwards'
import {loadDemoProfile,profileKey,resolveDemoProfile,updateDemoProfile,type DemoOwner,type DemoProfile} from './demoProfile'
import {exampleValues,isCompetitionNotice,leaveDays,proposedFilename,reviewForm,scenarioFields,scenarios,validateFilename,type FormValues,type Scenario} from './scenarios'

const account = useAccountStore()
const owner = ref<DemoOwner>('demo:forms')
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
const confirmValues = ref(false)
const reveal = ref(false)
const message = ref('')
const problem = ref('')
const imageVersion = ref(0)
const archive = computed(()=>profile.value.awards)
const reasonSuggestion = ref('')
const drafts = new Map<string,{values:FormValues;photo:string;name:string}>()


const review = computed(()=>reviewForm(scenario.value,values.value,Boolean(photo.value)))
const count = computed(()=>Object.keys(review.value.errors).length)
const groups = computed(()=>scenario.value.groups.map(group=>({
  ...group,fields:showAll.value?group.fields:group.fields.filter(field=>completion.value.includes(field.id)),
})).filter(group=>group.fields.length))
watch(review,result=>{
  for (const id of Object.keys(result.errors)) if (!completion.value.includes(id)) completion.value.push(id)
})
const filename = computed(()=>nameOverride.value || proposedFilename(scenario.value,values.value))
const filenameError = computed(()=>validateFilename(filename.value))
const filenamePreview = computed(()=>(filename.value.startsWith('演示-')?'':'演示-')+filename.value+'.'+scenario.value.format)
const days = computed(()=>leaveDays(values.value))
const competition = computed(()=>isCompetitionNotice(notice.value))

function changed() {
  confirmValues.value = false
  message.value = ''
  problem.value = ''
}

function select(next: Scenario, saveCurrent = true) {
  if (saveCurrent) drafts.set(scenario.value.id,{values:{...values.value},photo:photo.value,name:nameOverride.value})
  scenario.value = next
  const draft = drafts.get(next.id)
  values.value = draft ? {...draft.values} : resolveDemoProfile(next,profile.value)
  photo.value = draft?.photo || ''
  photoInput.value = undefined
  imageVersion.value++
  zoom.value = 1
  vertical.value = 50
  nameOverride.value = draft?.name || ''
  reasonSuggestion.value = ''
  preview.value = false
  reveal.value = false
  showAll.value = false
  completion.value = Object.keys(review.value.errors)
  changed()
}

async function switchOwner(next: DemoOwner) {
  const version = ++loadVersion
  owner.value = next
  ready.value = false
  drafts.clear()
  profile.value = {revision:0,values:{},awards:[]}
  select(scenario.value,false)
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
onMounted(()=>void switchOwner(owner.value))

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
  saving.value = true
  problem.value = ''
  try {
    profile.value = await updateDemoProfile(identity,profile.value.revision,edit)
    message.value = success
    return true
  } catch (error) {
    problem.value = error instanceof Error ? error.message : '本机资料保存失败。'
    try { profile.value = await loadDemoProfile(identity) } catch { /* Keep the draft editable. */ }
    return false
  } finally {
    saving.value = false
  }
}

async function saveCompletion() {
  if (count.value) return
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
  if (!await saveProfile(previous=>({...previous,values:{},awards:[]}),'本机演示资料已清除。')) return
  drafts.clear()
  select(scenario.value,false)
  message.value = '本机演示资料已清除。'
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

function download() {
  if (!confirmValues.value || !ready.value || saving.value || account.signedIn) return
  try {
    const result = buildForm(scenario.value,{...values.value},photo.value,filename.value)
    const url = URL.createObjectURL(result.blob)
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    link.click()
    window.setTimeout(()=>URL.revokeObjectURL(url),15_000)
    message.value = scenario.value.photo==='physical'
      ? '演示文件已生成。请打印后按校方要求贴照，再办理提交。'
      : '演示文件已生成，未向学校提交。'
  } catch (error) {
    problem.value = error instanceof Error ? error.message : '导出失败，请重试。'
  }
}

function displayed(value: string, sensitive?: boolean) {
  return !value ? '待补充' : sensitive && !reveal.value ? '•••• '+value.slice(-4) : value
}
</script>

<template>
  <main class="form-demo">
    <header class="intro">
      <RouterLink to="/me">← 返回我的</RouterLink>
      <p class="eyebrow">有绪 CampusWeave · 离线演示</p>
      <h1>智能填表</h1>
      <p>选择真实校园事务样例，补齐字段、预览并下载可编辑文件。请使用合成资料和图片。</p>
    </header>

    <section v-if="account.signedIn" class="panel">
      <p>这组样本仅在离线演示身份下开放。可从「我的」返回演示模式。</p>
    </section>

    <template v-else>
      <section class="panel">
        <label class="field">演示资料身份
          <select :value="owner" :disabled="saving || !ready" @change="switchOwner(($event.target as HTMLSelectElement).value as DemoOwner)">
            <option value="demo:forms">本机演示身份</option>
            <option value="demo:empty">独立空资料测试身份</option>
          </select>
        </label>
        <p>按身份分开保存。合成样例需主动加载。</p>
      </section>
      <nav class="scenarios" aria-label="演示场景">
        <button v-for="item in scenarios" :key="item.id" type="button" :aria-pressed="scenario.id===item.id" :disabled="!ready || saving" @click="select(item)">
          <strong>{{ item.title }}</strong><small>{{ item.format.toUpperCase() }}</small>
        </button>
      </nav>

      <section class="panel" aria-label="模板来源">
        <h2>{{ scenario.title }}</h2>
        <p>{{ scenario.provenance }} · <a :href="scenario.source" target="_blank" rel="noopener noreferrer">{{ scenario.school }}</a></p>
        <p>人工办理：{{ scenario.manual }}</p>
        <p v-if="scenario.printNote" class="warning">{{ scenario.printNote }}</p>
        <div class="actions">
          <button type="button"  :disabled="!ready || saving" @click="fillExamples">用合成资料补齐缺项</button>
          <button type="button"  :disabled="!ready || saving" @click="clearRemembered">清除本机演示资料</button>
        </div>
      </section>

      <details class="panel">
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
          <p aria-live="polite">{{ count ? count+' 项待补充或修正' : '申请人字段已齐全' }}</p>
        </div>
        <div class="actions">
          <button type="button" @click="showAll=!showAll">{{ showAll ? '只显示补录字段' : '显示并编辑整张表单' }}</button>
        </div>
        <p v-if="!groups.length">本次没有资料缺项。可预览，或打开整表修改。</p>
        <fieldset v-for="group in groups" :key="group.title" :disabled="saving || !ready">
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
              <small>{{ profileKey(scenario,field) ? '保存补录后可在适用场景复用' : '仅用于本次表单' }}</small>
            </div>
          </div>
        </fieldset>
        <section v-if="scenario.id==='scholarship'" class="award-archive" aria-label="演示经历档案">
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
          <button type="button" @click="suggestReason">起草申请理由</button>
          <div v-if="reasonSuggestion">
            <p>{{ reasonSuggestion }}</p>
            <button type="button" @click="useReason">使用这份理由</button>
          </div>
        </section>
        <p v-if="scenario.id==='leave' && days>0">请假 {{ days }} 天，含起止当日。</p>
        <ul v-if="review.reminders.length"><li v-for="reminder in review.reminders" :key="reminder">{{ reminder }} <a :href="scenario.source" target="_blank" rel="noopener noreferrer">校方依据</a></li></ul>

        <p v-if="scenario.photo==='physical'" class="warning">
          {{ scenario.photoNote || '照片需打印后粘贴。导出保留照片框。' }}
          <a :href="scenario.source" target="_blank" rel="noopener noreferrer">校方依据</a>
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
          <input :placeholder="proposedFilename(scenario,values)" :value="nameOverride" @input="nameOverride=($event.target as HTMLInputElement).value; changed()">
        </label>
        <p class="file-name">{{ filenamePreview }}</p>
        <p v-if="filenameError" class="warning">{{ filenameError }}</p>
        <div class="actions">
          <button type="button" class="primary" :disabled="Boolean(count) || saving || !ready" @click="saveCompletion">保存补录并预览</button>
          <button type="button" :disabled="!ready || saving" @click="preview=!preview; confirmValues=false">{{ preview?'收起字段预览':'预览填写内容' }}</button>
        </div>
      </section>

      <section v-if="preview" class="panel" aria-label="导出预览">
        <h2>导出内容预览</h2>
        <p>此处预览填写值。实际版式以 Excel 或 Word 中打开的文件为准。</p>
        <dl v-for="group in scenario.groups" :key="group.title" class="preview-values">
          <template v-for="field in group.fields" :key="field.id">
            <dt>{{ field.label }}</dt><dd>{{ displayed(values[field.id],field.sensitive) }}</dd>
          </template>
        </dl>
        <p v-if="scenario.photo==='physical'">照片框留空。打印后请按<a :href="scenario.source" target="_blank" rel="noopener noreferrer">校方说明</a>粘贴照片。</p>
        <img v-if="scenario.photo==='embedded' && photo" class="preview-photo" :src="photo" alt="导出照片预览">
        <label class="toggle"><input v-model="confirmValues" type="checkbox" :disabled="Boolean(count || filenameError) || !ready || saving"> 我确认这份演示文件的填写值和文件名</label>
        <button type="button" class="primary" :disabled="!confirmValues || Boolean(count || filenameError) || !ready || saving" @click="download">确认并下载 {{ scenario.format.toUpperCase() }}</button>
      </section>
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
.file-name{overflow-wrap:anywhere}
.feedback{position:sticky;bottom:4rem;padding:.65rem;border-radius:.5rem;background:#eef5ff}
@media(max-width:480px){.fields{grid-template-columns:1fr}.form-demo{padding-inline:.7rem}}
</style>
