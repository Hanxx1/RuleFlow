<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {requirePrivacyReview} from '../../services/privacyGuard'
import {readNotice,type NoticeSelection} from './noticeIntake'
import {mappedFields} from './genericForm'
import {accountFacts,assistantError,checkAssistantValue,proposedValue,requestFormAssistant,
  type Approved,type AssistField,type Plan,type Question,type Source} from './formAssistant'
import {scenarioFields,type FormValues} from './scenarios'

const props = defineProps<{intake:NoticeSelection;owner:string;values:FormValues;disabled:boolean}>()
const emit = defineEmits<{apply:[entries:Approved[]];requirement:[fieldId:string,plan:Plan,refs:Source[]]}>()
const open = ref(false)
const busy = ref(false)
const consent = ref(false)
const message = ref('')
const failure = ref('')
const plans = ref<Plan[]>([])
const questions = ref<Question[]>([])
const answers = ref<Record<string,string>>({})
const notes = ref('')
const includeFilled = ref(false)
const questionIds = new Map<string,string>()
const available = ref<Source[]>([])
const selected = ref<string[]>([])
const materials = ref<Source[]>([])
const picked = ref<string[]>([])
const resultSources = ref<Source[]>([])
const reviewed = ref<string[]>([])
const replacement = ref<{id:string;previous:string}>()
let operation:AbortController | undefined
let materialNumber = 0
let active = true

const strategy = {direct:'读取资料',retrieve:'提取材料',derive:'程序计算',integrate:'整合资料',
  generate:'AI 起草',ask:'需要补充',manual:'人工处理',skip:'不适用'}
const fields = computed(()=>(props.intake.genericMapping ? mappedFields(props.intake.genericMapping) : []).map((item,index)=>({
  id:'f'+index,field:scenarioFields(props.intake.scenario).find(f=>f.id===item.field.id) || item.field,
  writable:Boolean(item.slot) && !item.field.sensitive,where:item.where,label:item.label,context:item.context,
})))
const manual = computed(()=>props.intake.genericMapping?.form.manual || [])
const original = computed<Source[]>(()=>[
  ...fields.value.map(({id,where,label,context}):Source=>({
    id:'o'+id,kind:'original',locator:where.slice(0,250),text:[label.trim(),context?.trim()].filter(Boolean).join('\n').slice(0,800),
  })),
  ...manual.value.slice(0,18).map((item,i):Source=>({
    id:'m'+i,kind:'original',locator:item.where.slice(0,250),text:item.text.trim() || '原表保留区域',
  })),
])
const notice = computed<Source[]>(()=>{
  // Keep original line ranges and bound the text sent for each batch.
  const lines = (props.intake.noticeText || '').slice(0,24000).split(/\r?\n/)
  const blocks:Source[] = []
  let text='',start=0,last=0
  for (const [i,line] of lines.entries()) {
    if (!text && !line.trim()) continue
    const part=line.slice(0,1400)
    if (text && text.length+part.length+1>1600) {
      blocks.push({id:'n'+start,kind:'notice',locator:'通知 · 第 '+start+' 至 '+last+' 行',text:text.trim()})
      text=''
    }
    if (!text) start=i+1
    text+=(text?'\n':'')+part
    last=i+1
    if (line.length>1400) {
      blocks.push({id:'n'+start,kind:'notice',locator:'通知 · 第 '+start+' 至 '+last+' 行摘录',text:text.trim()})
      text=''
    }
  }
  if (text.trim()) blocks.push({id:'n'+start,kind:'notice',locator:'通知 · 第 '+start+' 至 '+last+' 行',text:text.trim()})
  return blocks.slice(0,28)
})
function fieldFor(plan:Plan) {return fields.value.find(field=>field.id===plan.id)}
const questionKey = (question:Question) => question.text.normalize('NFKC').replace(/\s/g,'')
const sources = computed<Source[]>(()=>[
  ...notice.value,...original.value,
  ...available.value.filter(source=>selected.value.includes(source.id)),
  ...materials.value.filter(source=>selected.value.includes(source.id)),
  ...(includeFilled.value ? fields.value.flatMap((row):Source[]=>{
    const value=props.values[row.field.id]?.trim()
    return row.writable && value ? [{id:'filled:'+row.id,kind:'answer',locator:'当前已填写 · '+row.field.label,
      text:value.slice(0,2000)}] : []
  }) : []),
  ...questions.value.flatMap((question):Source[]=>{
    const answer = answers.value[questionKey(question)]?.trim()
    return answer ? [{id:questionIds.get(questionKey(question))!,kind:'answer',locator:question.text,text:answer}] : []
  }),
  ...(notes.value.trim()?[{id:'notes',kind:'answer' as const,locator:'本次补充说明',text:notes.value.trim()}]:[]),
])
watch(sources,()=>{consent.value=false},{flush:'sync'})
onBeforeUnmount(()=>{active=false;operation?.abort()})

async function readFacts() {
  if (busy.value) return
  failure.value=''
  busy.value=true
  try {
    const next = await accountFacts(props.owner,props.intake.caseId || '')
    if (!active) return
    available.value = next.filter(item=>item.text.trim()).slice(0,40)
    selected.value = selected.value.filter(id=>materials.value.some(item=>item.id===id))
    message.value=available.value.length ? '可勾选与本次表单相关的资料。' : '暂无可用的已确认画像或经历。'
  } catch {
    if (active) failure.value='暂时无法读取本机资料。'
  } finally {busy.value=false}
}

async function addMaterial(event:Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value=''
  if (!file || busy.value) return
  if (materials.value.length>=6) {failure.value='一次最多选 6 份材料摘录。';return}
  busy.value=true
  failure.value=''
  try {
    const text = await readNotice(file)
    if (active) materials.value.push({id:'material'+materialNumber++,kind:'material',
      locator:file.name.slice(0,230)+' · 开头摘录',text:text.trim().slice(0,1800)})
  } catch {if(active)failure.value='无法读取材料正文，可将相关事实粘贴到本次补充说明。'}
  finally {busy.value=false}
}

function prepareReplacement(plan:Plan) {
  const row=fieldFor(plan)
  if (!row?.writable) return
  replacement.value={id:row.id,previous:props.values[row.field.id] || ''}
  consent.value=false
  message.value='已选择重做「'+row.field.label+'」。核对发送内容后重新生成，原值会保留到你确认替换。'
}

async function run(stage:'analyze'|'generate') {
  if (!active || busy.value || !consent.value) return
  const replace = stage==='generate' ? replacement.value : undefined
  const rows = replace ? fields.value.filter(row=>row.id===replace.id) : fields.value
  const requested:AssistField[] = rows.map(row=>({
    id:row.id,label:row.label.trim().slice(0,250),source_id:'o'+row.id,writable:row.writable,
    choices:row.field.choices,min_chars:row.field.min,max_chars:row.field.max,
    locked:Boolean(props.values[row.field.id]?.trim()) && row.id!==replace?.id,
  }))
  if (!requested.length) return
  busy.value=true
  failure.value=message.value=''
  const snapshot = sources.value.filter(source=>!replace || source.id!=='filled:'+replace.id)
    .map(source=>({...source}))
  const controller = new AbortController()
  operation=controller
  try {
    const privacy = await requirePrivacyReview(snapshot.map(source=>source.locator+'\n'+source.text).join('\n\n'),[], '',consent.value)
    if (!active || !consent.value) return
    if (privacy.finding_types.length && !window.confirm('预览内容可能含'+privacy.finding_types.join('、')+'。确定授权本次发送？')) return
    consent.value=false
    const next:Plan[] = []
    const common = new Map<string,Question>()
    for (let start=0;start<requested.length;start+=12) {
      if (controller.signal.aborted) return
      const batch=requested.slice(start,start+12)
      const ids=new Set(batch.map(field=>field.source_id))
      const blocks=snapshot.filter(source=>!source.id.startsWith('of') || ids.has(source.id))
      const result = await requestFormAssistant(stage,props.intake.attachment.slice(0,250),batch,blocks,controller.signal)
      next.push(...result.fields)
      for (const question of result.questions) {
        const key=questionKey(question)
        const prior=common.get(key)
        common.set(key,{text:question.text,fields:[...new Set([...(prior?.fields || []),...question.fields])]})
      }
    }
    if (!active) return
    plans.value=replace ? plans.value.map(row=>row.id===replace.id ? next[0] : {...row,value:null,calculation:null}) : next
    for (const key of common.keys()) if (!questionIds.has(key)) questionIds.set(key,'a'+questionIds.size)
    questions.value=[...new Map([...questions.value.filter(q=>answers.value[questionKey(q)]?.trim()),
      ...common.values()].map(q=>[questionKey(q),q])).values()]
    resultSources.value=snapshot
    reviewed.value=[]
    picked.value=next.filter(plan=>candidate(plan) && !problem(plan)).map(plan=>plan.id)
    message.value=stage==='analyze' ? '已分析本表。你可以补充下方问题，也可直接生成候选。' :
      picked.value.length ? '已生成候选。请逐项核对原文和使用的事实，再确认带入。' : '当前没有可直接带入的候选，请补充资料或手工填写。'
    if (stage==='analyze') replacement.value=undefined
  } catch(error) {
    if (active) failure.value=assistantError(error)
  } finally {operation=undefined;busy.value=false}
}

function candidate(plan:Plan) {
  const row=fieldFor(plan)
  if (!row?.writable) return ''
  const current=props.values[row.field.id] || ''
  if (current.trim() && (replacement.value?.id!==plan.id || replacement.value.previous!==current)) return ''
  if ([...plan.facts,...(plan.calculation?.operands || [])].some(cite=>{
    const previous=reference(cite.source_id)
    return previous && !sources.value.some(item=>item.id===previous.id && item.text===previous.text)
  })) return ''
  return proposedValue(plan)
}
function problem(plan:Plan) {
  const row=fieldFor(plan)
  return row ? checkAssistantValue(row.field,plan,candidate(plan) || props.values[row.field.id] || '') : ''
}
function reference(id:string) {return resultSources.value.find(source=>source.id===id)}
function approveRequirement(plan:Plan) {
  const row=fieldFor(plan)
  if (!row?.writable || plan.role!=='applicant' || plan.ambiguous || plan.applicability==='unknown') return
  const ids=new Set(plan.requirements.map(cite=>cite.source_id))
  emit('requirement',row.field.id,plan,resultSources.value.filter(source=>ids.has(source.id)))
  reviewed.value.push(plan.id)
}
function apply() {
  const updates = plans.value.flatMap((plan):Approved[]=>{
    const row=fieldFor(plan)
    if (!row || !picked.value.includes(plan.id) || problem(plan)) return []
    const value=candidate(plan)
    if (!value) return []
    if (props.values[row.field.id]?.trim() &&
        !window.confirm('用此候选替换「'+row.field.label+'」当前内容？')) return []
    const ids=new Set([...plan.facts,...(plan.calculation?.operands || []),...plan.requirements].map(cite=>cite.source_id))
    return [{fieldId:row.field.id,plan,value,references:resultSources.value.filter(source=>ids.has(source.id))}]
  })
  emit('apply',updates)
  message.value=updates.length ? '已带入 '+updates.length+' 项。你仍可修改或核对导出预览。' : '当前没有可带入的项目。'
  picked.value=[]
  replacement.value=undefined
}
</script>

<template>
  <section class="assistant-panel" aria-label="智能填写整份表单">
    <h3>智能填写整份表单</h3>
    <p v-if="!owner">登录后可使用模型分析。你也可以在下方手工填写。</p>
    <button v-else-if="!open" type="button" :disabled="disabled" @click="open=true">打开智能填写</button>
    <fieldset v-else :disabled="busy || disabled">
      <legend>选择资料并核对发送范围</legend>
      <button type="button" @click="readFacts">查看本机已确认画像和经历</button>
      <label v-for="item in available" :key="item.id">
        <input v-model="selected" type="checkbox" :value="item.id"> {{ item.locator }} · {{ item.text }}
      </label>
      <label>添加相关材料摘录（TXT 或 DOCX）<input type="file" accept=".txt,.docx" @change="addMaterial"></label>
      <label v-for="item in materials" :key="item.id">
        <input v-model="selected" type="checkbox" :value="item.id"> {{ item.locator }}
      </label>
      <label v-for="question in questions" :key="questionKey(question)">{{ question.text }}
        <small>用于 {{ question.fields.map(id=>fields.find(field=>field.id===id)?.field.label).filter(Boolean).join('、') }}</small>
        <textarea v-model="answers[questionKey(question)]" maxlength="800" rows="2"></textarea>
      </label>
      <label><input v-model="includeFilled" type="checkbox"> 允许引用当前已填写的普通字段</label>
      <label>本次补充说明（选填）<textarea v-model="notes" maxlength="1800" rows="3"></textarea></label>
      <details>
        <summary>查看将发送的通知、原表片段和选中资料</summary>
        <p>通知长行和材料只发送所显示的摘录。请移除与本次无关的资料。</p>
        <ul><li v-for="item in sources" :key="item.id"><strong>{{ item.locator }}</strong><p>{{ item.text }}</p></li></ul>
      </details>
      <label><input v-model="consent" type="checkbox"> 我已核对上述文本，同意本次发送到已配置的模型服务。</label>
      <div class="assistant-actions">
        <button type="button" :disabled="!consent" @click="run('analyze')">分析整份表单</button>
        <button type="button" :disabled="!consent" @click="run('generate')">
          {{ replacement ? '重新生成所选字段' : '生成整表候选' }}
        </button>
      </div>
    </fieldset>
    <p v-if="busy" role="status">正在处理，请稍候。</p>
    <p v-if="failure" role="alert">{{ failure }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <fieldset v-if="plans.length" :disabled="busy || disabled">
      <legend>字段要求与候选</legend>
      <article v-for="plan in plans" :key="plan.id">
        <h4>{{ fieldFor(plan)?.field.label }}</h4>
        <p>{{ plan.meaning }} · {{ strategy[plan.strategy] }}</p>
        <small>{{ {required:'必填',optional:'选填',conditional:'按条件填写',unknown:'必填性待核对'}[plan.required] }}</small>
        <p>{{ plan.expected }}</p>
        <small v-if="plan.condition">适用条件 · {{ plan.condition }} · {{ {applies:'适用',unknown:'待核对',not_applicable:'不适用'}[plan.applicability] }}</small>
        <small v-if="plan.bounds.min_chars!=null || plan.bounds.max_chars!=null">
          模型识别的字数要求 · {{ plan.bounds.min_chars!=null ? '至少 '+plan.bounds.min_chars+' 字 ' : '' }}
          {{ plan.bounds.max_chars!=null ? '最多 '+plan.bounds.max_chars+' 字' : '' }} · 请核对原文
        </small>
        <small v-if="plan.bounds.earliest_date || plan.bounds.latest_date">
          日期范围 · {{ plan.bounds.earliest_date || '不限起始' }} 至 {{ plan.bounds.latest_date || '不限结束' }}
        </small>
        <small v-if="plan.bounds.minimum_number!=null || plan.bounds.maximum_number!=null">
          数值范围 · {{ plan.bounds.minimum_number ?? '不限下界' }} 至 {{ plan.bounds.maximum_number ?? '不限上界' }}
        </small>
        <small v-if="plan.bounds.format_note">{{ plan.bounds.format_note }} · 请对照原文确认</small>
        <p v-if="!fieldFor(plan)?.writable || plan.role!=='applicant' || plan.ambiguous">此项需人工核对填写主体或位置。</p>
        <p v-else-if="problem(plan)" class="warning">{{ problem(plan) }}</p>
        <label v-if="candidate(plan)"><input v-model="picked" type="checkbox" :value="plan.id" :disabled="Boolean(problem(plan))"> 选择带入以下内容</label>
        <p v-if="candidate(plan)" class="candidate">{{ candidate(plan) }}</p>
        <details>
          <summary>核对原文及使用的事实</summary>
          <ul>
            <li v-for="(cite,index) in [...plan.requirements,...plan.facts,...(plan.calculation?.operands || [])]" :key="index">
              {{ reference(cite.source_id)?.locator }} · {{ cite.quote }}
            </li>
          </ul>
        </details>
        <button v-if="fieldFor(plan)?.writable && plan.role==='applicant' && !plan.ambiguous && plan.applicability!=='unknown'"
          type="button" :disabled="reviewed.includes(plan.id)" @click="approveRequirement(plan)">采用已核对的字段要求</button>
        <button v-if="fieldFor(plan)?.writable" type="button" @click="prepareReplacement(plan)">选择重做此字段</button>
      </article>
      <button type="button" :disabled="!picked.length" @click="apply">确认带入所选候选</button>
    </fieldset>
  </section>
</template>

<style scoped>
.assistant-panel{border:1px solid #d8e4f0;border-radius:.7rem;padding:.8rem;margin:1rem 0}
.assistant-panel fieldset{min-width:0;margin:.75rem 0;padding:.65rem}
.assistant-panel label,.assistant-panel small{display:block;margin:.35rem 0;overflow-wrap:anywhere}
.assistant-panel textarea{display:block;width:100%;box-sizing:border-box;margin:.25rem 0}
.assistant-panel article{border-top:1px solid #e3eaf2;padding:.7rem 0;overflow-wrap:anywhere}
.assistant-actions{display:flex;gap:.5rem;flex-wrap:wrap}
.candidate{white-space:pre-wrap}
</style>
