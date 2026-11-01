<script setup lang="ts">
import {onMounted,ref,computed} from 'vue';
import {useAccountStore} from '../stores/account';
import {useCasesStore} from '../stores/cases';
import {loadWorkspace,emptyWorkspace} from '../services/clientWorkspace';
import {expandCourses,localSchedule} from '../services/timetable';
const props=defineProps<{tasks:any[]}>(),account=useAccountStore(),cases=useCasesStore(),data=ref(emptyWorkspace(account.user?.id||'offline')),from=ref(new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai'}).format(new Date())),duration=ref<Record<string,number>>({}),preview=ref<any>(null),error=ref('');
const to=computed(()=>{const day=new Date(from.value+'T00:00:00Z');day.setUTCDate(day.getUTCDate()+13);return day.toISOString().slice(0,10)});
const courses=computed(()=>{try{return expandCourses(data.value.courses,from.value,to.value)}catch{return []}});
onMounted(async()=>{data.value=await loadWorkspace(account.user?.id||'offline')});
async function run(){try{data.value=await loadWorkspace(account.user?.id||'offline');preview.value=localSchedule(props.tasks.map(t=>({...t,duration_minutes:duration.value[t.id]||t.duration_minutes})),data.value.courses,from.value,to.value,[],cases.plan?.edges||[])}catch(e:any){error.value=e.message}}
</script>
<template><section class="surface-card" aria-label="本机课表与离线预览"><h2>课表占用与本机演示</h2><RouterLink to="/timetable" class="text-link">查看修改课表</RouterLink><label>预览起始日期<input v-model="from" type="date" @change="preview=null"></label><p>{{courses.length}} 个课程时段；按北京时间展开单双周。</p><article v-for="c in courses" :key="c.id"><b>{{c.title}}</b><p>{{c.starts_at.slice(0,16)}}–{{c.ends_at.slice(11,16)}}</p><small>{{c.quote}}</small></article><details v-if="!account.signedIn"><summary>离线课表避让演示（不保存到账户）</summary><label v-for="task in tasks.filter(t=>!['done','skipped'].includes(t.status))" :key="task.id">{{task.title}}耗时分钟<input v-model.number="duration[task.id]" type="number" min="1" max="1440"></label><button class="button button--secondary" @click="run">按课表预览离线任务</button><p v-if="error" role="alert">{{error}}</p><template v-if="preview"><p>可安排 {{preview.suggestions.length}} 项，待补充/未安排 {{preview.unscheduled.length}} 项。</p><article v-for="b in preview.suggestions" :key="b.task_id"><b>{{b.title}}</b><p>{{b.starts_at}}—{{b.ends_at}}</p></article><p v-for="u in preview.unscheduled" :key="u.task_id">{{u.title}}：{{({missing_evidence:'缺少任务证据',duration_required:'请填写预计耗时',dependency_blocked:'前置步骤未安排或未完成',no_available_slot:'截止前没有足够空闲时段'} as Record<string,string>)[u.reason]||'待核对'}}</p></template></details></section></template>
<style scoped>label{display:block;margin:8px 0}input{max-width:100%}small{overflow-wrap:anywhere}article{border-top:1px solid #ddd;padding:8px 0}</style>
