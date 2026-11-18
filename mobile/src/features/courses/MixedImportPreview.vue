<script setup lang="ts">
import {computed,ref} from 'vue';
import {createMixedReviewSamples} from './mixedReviewSamples';
import {allowedOperations,editMixedItem,kindLabels,operationLabels,resolveSampleReceipt,reviewIssue,simulateMixedReview,statusLabels,type MixedCandidate,type MixedOperation,type SampleScenario} from './mixedReviewModel';
const props=defineProps<{courseContext?:string}>();
const review=ref(createMixedReviewSamples()),scenario=ref<SampleScenario>('partial'),notice=ref('');
const context=computed(()=>review.value.courses.find(course=>course.id===props.courseContext));
const selected=computed(()=>review.value.items.filter(item=>item.selected));
const counts=computed(()=>({success:review.value.items.filter(item=>item.status==='success').length,failed:review.value.items.filter(item=>item.status==='failed').length,unknown:review.value.items.filter(item=>item.status==='unknown').length}));
function edit(id:string,patch:Parameters<typeof editMixedItem>[2]){try{review.value=editMixedItem(review.value,id,patch);notice.value=''}catch(e){notice.value=(e as Error).message}}
function locked(item:MixedCandidate){return item.status==='success'||item.status==='unknown'}
function run(ids=selected.value.map(item=>item.id)){review.value=simulateMixedReview(review.value,ids,scenario.value);notice.value='已更新模拟结果，所有正式业务数据均未修改。'}
function query(id:string){review.value=resolveSampleReceipt(review.value,id);notice.value='已查询样例回执；首次成功项没有再次执行。'}
function reset(){review.value=createMixedReviewSamples();notice.value='已取消并清空本页核对与模拟结果，没有写入正式数据。'}
function checked(event:Event){return (event.target as HTMLInputElement).checked}
function value(event:Event){return (event.target as HTMLInputElement).value}
</script>

<template>
  <main class="mixed page">
    <header><p class="brand">有绪 CampusWeave · 繁事有绪，办事有方。</p><h1>逐项核对导入建议</h1><p>一份通知可以包含多门课程与校园事务，先核对，再决定每项如何处理。</p></header>
    <aside class="sample-note"><strong>合成样例 · 不是真实分析结果</strong><p>本页只验证核对与结果展示，不调用 AI、不读取账户资料、不保存到本机或服务端。正式保存、任务、资料和事项确认能力待接入；刷新后重置。</p></aside>
    <nav aria-label="样例入口"><a href="/mixed-import-preview.html">统一导入样例</a><a href="/mixed-import-preview.html?course=sample-linear">线性代数课程入口样例</a></nav>
    <p v-if="context" class="context">来自 {{context.term}} · {{context.name}}。这只是入口上下文，各项归属仍须分别核对，不会全部归入当前课。</p><p v-else>来自统一导入入口样例，各项归属由用户逐项核对。</p>
    <section class="panel source-panel"><h2>合成来源原文</h2><p v-for="source in review.sources" :key="source.id">{{source.text}}</p><p>以下原句只对应合成输入，不能作为真实办理依据。</p></section>
    <p role="status">已选择 {{selected.length}} 项；样例成功 {{counts.success}} 项，失败 {{counts.failed}} 项，结果未知 {{counts.unknown}} 项。</p>
    <p v-if="notice" role="status" class="notice">{{notice}}</p>
    <section class="candidate-list" aria-label="混合建议列表">
      <article v-for="item in review.items" :key="item.id" class="panel candidate" :data-candidate="item.id">
        <div class="heading"><label class="selection"><input type="checkbox" :checked="item.selected" :disabled="locked(item)" :aria-label="'选择'+item.title" @change="edit(item.id,{selected:checked($event)})"><span>{{kindLabels[item.kind]}}</span></label><span class="state">{{statusLabels[item.status]}}</span></div>
        <h2>{{item.title}}</h2><p class="quote">原句：{{item.quote}}</p><p v-if="!review.sources.some(source=>source.id===item.sourceId)" class="error">来源缺失，待核对，不能执行。</p>
        <p class="unknown">适用性：{{item.eligibility==='UNKNOWN'?'待核对':'已核对'}}；{{item.missingFields.join('、')}}。选择或模拟确认不会改变资格结论。</p>
        <section v-if="locked(item)" class="decision" aria-label="本项只读核对结果"><p>已核对归属：{{item.target==='campus'?'普通校园事务':review.courses.find(course=>course.id===item.target)?.term+' · '+review.courses.find(course=>course.id===item.target)?.name}}</p><p>已选操作：{{operationLabels[item.operation]}}</p><p>本次内容：{{item.content}}</p><p v-if="item.existing?.target===item.target">确认前记录：{{item.existing.value}}</p><p>当前结果不可改写；结果未知时请先查询回执。</p></section>
        <fieldset v-else>
          <label>建议归属<select aria-label="建议归属" :value="item.target" @change="edit(item.id,{target:value($event)})"><option v-if="item.kind==='case'" value="campus">普通校园事务</option><template v-else><option v-for="course in review.courses" :key="course.id" :value="course.id">{{course.term}} · {{course.name}}</option></template></select></label>
          <label>处理方式<select aria-label="处理方式" :value="item.operation" @change="edit(item.id,{operation:value($event) as MixedOperation})"><option v-for="operation in allowedOperations(item)" :key="operation" :value="operation">{{operationLabels[operation]}}</option></select></label>
          <label>本次内容<textarea aria-label="本次内容" :value="item.content" maxlength="2000" @input="edit(item.id,{content:value($event)})"></textarea></label><p class="muted">可人工整理内容，原句保持不变；修改后的内容仍需核对。</p>
          <div v-if="item.existing?.target===item.target" class="conflict"><h3>{{item.kind==='requirement'?'要求存在冲突':'疑似重复记录'}}</h3><p>{{item.existing.title}}：{{item.existing.value}}</p><p>本次建议：{{item.content}}</p><label class="selection"><input type="checkbox" :checked="item.acknowledged" @change="edit(item.id,{acknowledged:checked($event)})"><span>我已核对现有记录及本次操作</span></label><p>修改内容、归属或处理方式后需重新核对。</p></div>
        </fieldset>
        <p v-if="reviewIssue(review,item)" class="error">{{reviewIssue(review,item)}}</p>
        <p v-if="item.dependsOn.length">先决条件：{{item.dependsOn.map(id=>review.items.find(other=>other.id===id)?.title||'无效建议').join('、')}}。这表示建议执行顺序，不会创建任务依赖或日程占用。</p>
        <p v-if="item.message" role="status">{{item.message}}</p>
        <p class="muted">本项样例执行 {{item.attempts}} 次</p>
        <button v-if="item.status==='failed'" type="button" class="button button--secondary" :disabled="!item.selected" @click="run([item.id])">仅重试本项样例</button>
        <button v-if="item.status==='blocked'" type="button" class="button button--secondary" :disabled="!item.selected" @click="run([item.id])">重新核对并继续本项</button>
        <button v-if="item.status==='unknown'" type="button" class="button button--secondary" @click="query(item.id)">查询样例回执</button>
      </article>
    </section>
    <section class="panel controls" aria-label="模拟确认操作"><h2>核对后模拟结果</h2><label>合成响应场景<select aria-label="合成响应场景" v-model="scenario"><option value="partial">部分失败，单项重试后成功</option><option value="unknown">响应丢失，查询后确认首次成功</option></select></label><p>只对已选且可执行的建议模拟。成功项不重复执行，结果未知项先查回执，前置未成功的项等待。模拟结果不代表实际办理完成。</p><div class="actions"><button type="button" class="button" :disabled="!selected.length" @click="run()">模拟确认所选建议</button><button type="button" class="button button--secondary" @click="reset">取消并重置核对</button></div></section>
  </main>
</template>

<style scoped>
.mixed{max-width:860px;margin:0 auto;padding:24px 18px 48px;overflow-wrap:anywhere}.mixed h1{font-size:28px}.mixed h2{font-size:19px;margin:12px 0}.mixed h3{font-size:15px}.mixed p{line-height:1.75;white-space:pre-wrap}.brand,.muted{color:#526b68;font-size:12px}.sample-note,.panel{padding:18px;border:1px solid #dce8e2;border-radius:16px;background:white}.sample-note{background:#e8f3ee}.mixed nav{display:flex;flex-wrap:wrap;gap:16px;margin:18px 0}.mixed a{color:#096b58}.candidate-list{display:grid;gap:16px;margin:16px 0}.heading,.selection,.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.heading{justify-content:space-between}.selection input{width:20px;height:20px;flex:none}.state{padding:5px 10px;border-radius:8px;background:#edf4f0;color:#285e50;font-size:12px}.quote{border-left:3px solid #81b4a7;padding-left:12px}.unknown,.context{color:#6b511a}.candidate fieldset{border:0;padding:0;margin:0;min-width:0}.candidate fieldset:disabled{opacity:.75}.candidate fieldset>label,.controls>label{display:grid;gap:8px;margin:12px 0}.mixed select,.mixed textarea{width:100%;min-width:0;border:1px solid #a5bdb3;border-radius:8px;padding:10px;font:inherit;color:#244a3e;background:white}.mixed textarea{min-height:90px;resize:vertical}.conflict{padding:14px;background:#fff5e6;border-radius:10px}.error{color:#a12c2c}.notice{background:#e8f3ee;padding:12px}.mixed :focus-visible{outline:3px solid #208c76;outline-offset:3px}.actions{margin-top:14px}.controls{margin-top:20px}@media(min-width:700px){.candidate-list{grid-template-columns:1fr 1fr}}@media(max-width:390px){.mixed{padding:18px 12px 36px}.panel{padding:14px}.mixed .button{white-space:normal}}
</style>
