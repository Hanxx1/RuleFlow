<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue';
import {RouterLink,useRoute,useRouter} from 'vue-router';
import AppHeader from '../components/AppHeader.vue';
import {guideChapters,guideTopic,quickStart,searchGuide,type GuideTopic} from '../content/guide';
import guideHero from '../assets/illustrations/hero_multi_source_import.webp';

const route=useRoute(),router=useRouter();
const query=ref(''),opened=ref(new Set<GuideTopic>());
const results=computed(()=>searchGuide(query.value));
const searching=computed(()=>Boolean(query.value.trim()));
const returnTo=computed(()=>{
  const from=typeof route.query.from==='string'?route.query.from:'';
  if(!/^\/(?!\/)/.test(from))return '/home';
  const resolved=router.resolve(from);
  return resolved.matched.length&&resolved.path!=='/guide'?from:'/home';
});
watch(query,()=>{opened.value=new Set(searching.value?results.value.chapters.map(chapter=>chapter.id):[guideTopic(route.query.topic)||'import'])});
watch(()=>route.query.topic,async value=>{
  const topic=guideTopic(value);
  opened.value=new Set([topic||'import']);
  if(!topic||typeof document==='undefined')return;
  query.value='';
  await nextTick();
  const element=document.getElementById(`guide-${topic}`);
  element?.scrollIntoView({block:'start'});
  element?.querySelector('summary')?.focus({preventScroll:true});
},{immediate:true});
async function chooseTopic(topic:GuideTopic){
  query.value='';
  if(route.query.topic!==topic){await router.replace({path:'/guide',query:{...route.query,topic}});return}
  opened.value=new Set([...opened.value,topic]);
  await nextTick();
  const element=document.getElementById(`guide-${topic}`);
  element?.scrollIntoView({block:'start'});
  element?.querySelector('summary')?.focus({preventScroll:true});
}
function toggle(topic:GuideTopic,event:Event){
  const next=new Set(opened.value);
  if((event.target as HTMLDetailsElement).open)next.add(topic);else next.delete(topic);
  opened.value=next;
}
function scrollDirectory(){document.getElementById('guide-directory-title')?.scrollIntoView({block:'start'})}
</script>

<template>
  <div class="page page--guide">
    <div class="guide-topbar">
      <AppHeader title="使用指南" subtitle="从第一份通知，到每一步行动">
        <template #action><RouterLink class="icon-button icon-button--plain" :to="returnTo" aria-label="返回原页面">←</RouterLink></template>
      </AppHeader>
    </div>

    <section class="guide-intro" aria-labelledby="guide-intro-title">
      <div><span class="guide-kicker">跟着做，就能上手</span><h2 id="guide-intro-title">让通知变成<br>清楚的下一步。</h2><p>先核对原文与资料，再确认日期和行动。遇到问题，按章节查找。</p></div>
      <img :src="guideHero" alt="" decoding="async">
    </section>

    <section class="guide-overview" aria-labelledby="guide-quick-title">
      <div class="guide-heading"><h2 id="guide-quick-title">第一次用，按这四步</h2><span>完整流程</span></div>
      <ol class="guide-flow">
        <li v-for="(step,index) in quickStart" :key="index"><button type="button" @click="chooseTopic(step.topic)"><span class="guide-flow__number" aria-hidden="true">{{index+1}}</span><span><strong>{{step.title}}</strong><small>{{step.description}}</small><span class="guide-flow__more">查看操作 <span aria-hidden="true">↗</span></span></span></button></li>
      </ol>
      <details class="guide-example">
        <summary>想先体验？用内置样例走一遍 <span aria-hidden="true">＋</span></summary>
        <div><p>先打开明确标记的综测离线样例，查看原文依据和相关性提示，再进入执行计划切换到该样例、体验步骤状态。样例中的日期和资料仅用于演示。</p><p>真实通知还需要登录后导入，并在“核对分析候选”中确认日期与步骤；离线样例不能代替这一确认流程。</p><RouterLink class="button button--small button--secondary" to="/cases/demo-assessment/analysis">打开离线样例</RouterLink></div>
      </details>
    </section>

    <section class="guide-browser" aria-labelledby="guide-directory-title">
      <div class="guide-heading"><h2 id="guide-directory-title">按你要做的事查找</h2><span>{{guideChapters.length}} 个章节</span></div>
      <label class="guide-search"><span>搜索指南</span><div><img src="/assets/icons/actions/icon_search.svg" alt=""><input v-model="query" type="search" placeholder="试试：附件、待确认、排程" maxlength="100" aria-controls="guide-results"><button v-if="query" type="button" @click="query=''">清空</button></div></label>
      <nav v-if="!searching" class="guide-directory" aria-label="指南目录"><button v-for="(chapter,index) in guideChapters" :key="chapter.id" type="button" @click="chooseTopic(chapter.id)"><span>{{String(index+1).padStart(2,'0')}}</span><b>{{chapter.title}}</b><span aria-hidden="true">›</span></button></nav>
      <p v-if="searching" class="guide-search-status" role="status">找到 {{results.chapters.length}} 个章节、{{results.faqs.length}} 个常见问题</p>
    </section>

    <div id="guide-results" class="guide-results">
      <div v-if="!results.chapters.length&&!results.faqs.length" class="guide-empty" role="status"><h2>暂时没有匹配内容</h2><p>试试更短的关键词，如“文件”“日期”“资料”或“隐私”。</p><button class="button button--small button--secondary" type="button" @click="query=''">查看全部指南</button></div>
      <details v-for="(chapter,index) in results.chapters" :id="`guide-${chapter.id}`" :key="chapter.id" class="guide-chapter" :open="opened.has(chapter.id)" @toggle="toggle(chapter.id,$event)">
        <summary><span class="guide-chapter__icon"><img :src="chapter.icon" alt=""></span><span class="guide-chapter__title"><span class="guide-kicker">{{searching?'操作指南':`第 ${index+1} 章`}}</span><h2>{{chapter.title}}</h2><span>{{chapter.summary}}</span></span><span class="guide-chevron" aria-hidden="true">⌄</span></summary>
        <div class="guide-chapter__body">
          <p class="guide-scene"><b>适用场景</b>{{chapter.scene}}</p>
          <ol class="guide-steps"><li v-for="(step,stepIndex) in chapter.steps" :key="step.title"><span aria-hidden="true">{{stepIndex+1}}</span><div><h3>{{step.title}}</h3><p>{{step.description}}</p></div></li></ol>
          <div class="guide-result"><h3>完成后，你会看到</h3><p>{{chapter.result}}</p></div>
          <aside class="guide-notes"><h3>操作前后，请留意</h3><ul><li v-for="note in chapter.notes" :key="note">{{note}}</li></ul></aside>
          <RouterLink class="button button--primary button--block guide-action" :to="chapter.action.to">{{chapter.action.label}} <span aria-hidden="true">→</span></RouterLink>
          <button class="guide-top-link" type="button" @click="scrollDirectory">返回目录 ↑</button>
        </div>
      </details>
    </div>

    <section v-if="results.faqs.length" class="guide-faq" aria-labelledby="guide-faq-title">
      <div class="guide-heading"><h2 id="guide-faq-title">遇到问题时</h2><span>常见问题</span></div>
      <details v-for="faq in results.faqs" :key="faq.id" :open="searching"><summary>{{faq.question}}<span class="guide-chevron" aria-hidden="true">⌄</span></summary><div><p>{{faq.answer}}</p><button class="guide-top-link" type="button" @click="chooseTopic(faq.topic)">查看对应操作 →</button></div></details>
    </section>

    <footer class="guide-footer"><h2>还需要帮助？</h2><p>记录页面和复现步骤，在帮助页复制诊断信息；分享前请核对个人信息。</p><RouterLink class="button button--secondary button--block" to="/help">帮助与反馈</RouterLink><RouterLink class="guide-top-link" :to="returnTo">返回原页面</RouterLink></footer>
  </div>
</template>

<style scoped>
.page--guide{overflow:visible}
.guide-topbar{position:sticky;z-index:30;top:0;margin:calc(-16px - env(safe-area-inset-top)) -16px 16px;padding:calc(16px + env(safe-area-inset-top)) 16px 12px;border-bottom:1px solid var(--color-border);background:rgba(245,250,249,.97)}
.guide-topbar :deep(.app-header){margin-bottom:0}
.guide-intro{display:grid;grid-template-columns:minmax(0,1fr) 100px;align-items:center;gap:8px;margin-bottom:24px;padding:22px 18px;border-radius:20px;background:linear-gradient(135deg,#dcf6ef,#e7f5ff)}
.guide-kicker{display:block;color:var(--color-primary-strong);font-size:12px;font-weight:700;line-height:1.5}
.guide-intro h2{margin-top:8px;font-size:25px;line-height:1.35}
.guide-intro p{margin-top:10px;font-size:13px;line-height:1.7}
.guide-intro img{width:100%;object-fit:contain}
.guide-heading{display:flex;min-width:0;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:12px}
.guide-heading h2{font-size:18px;line-height:1.5}
.guide-heading>span{flex:none;color:var(--color-text-secondary);font-size:12px}
.guide-flow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:0;padding:0;list-style:none}
.guide-flow li{min-width:0}
.guide-flow button{display:flex;width:100%;height:100%;min-width:0;align-items:flex-start;gap:9px;padding:14px 12px;border:1px solid var(--color-border);border-radius:15px;background:#fff;color:var(--color-text-primary);text-align:left;cursor:pointer}
.guide-flow__number{display:grid;width:23px;height:23px;flex:none;place-items:center;border-radius:8px;background:var(--color-primary-soft);color:var(--color-primary-strong);font-size:12px;font-weight:800}
.guide-flow button>span:last-child{min-width:0}
.guide-flow strong{display:block;font-size:14px;line-height:1.6}
.guide-flow small{display:block;margin-top:4px;color:var(--color-text-secondary);font-size:12px;line-height:1.65}
.guide-flow__more{display:block;margin-top:10px;color:var(--color-primary-strong);font-size:12px}
.guide-example{margin-top:12px;padding:14px;border:1px dashed #b0d5ca;border-radius:14px;background:#edf8f4}
.guide-example summary{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:13px;font-weight:650}
.guide-example p{margin-top:12px;font-size:13px}
.guide-example .button{margin-top:12px}
.guide-browser{margin-top:26px}
.guide-search{display:block;min-width:0}
.guide-search>span{display:block;margin-bottom:6px;font-size:13px;font-weight:650}
.guide-search>div{display:flex;min-width:0;align-items:center;gap:8px;padding:0 10px;border:1px solid var(--color-border);border-radius:13px;background:#fff}
.guide-search img{width:20px;height:20px;flex:none}
.guide-search input{min-width:0;flex:1;margin:0;padding:12px 0;border:0;border-radius:8px;background:transparent;font-size:14px}
.guide-search input:focus{box-shadow:none}
.guide-search>div:focus-within{outline:3px solid rgba(16,183,150,.24);outline-offset:2px}
.guide-search button{flex:none;padding:8px 2px;border:0;background:transparent;color:var(--color-primary-strong);font-size:12px;cursor:pointer}
.guide-directory{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}
.guide-directory button{display:flex;min-width:0;align-items:center;gap:7px;padding:11px 10px;border:1px solid var(--color-border);border-radius:12px;background:#fff;color:var(--color-text-primary);text-align:left;cursor:pointer}
.guide-directory button>span:first-child{flex:none;color:var(--color-primary);font-size:12px;font-weight:700}
.guide-directory b{min-width:0;flex:1;font-size:12px;font-weight:650;line-height:1.6;overflow-wrap:anywhere}
.guide-directory button>span:last-child{color:var(--color-text-secondary)}
.guide-search-status{margin-top:12px;font-size:13px}
.guide-results{display:grid;gap:12px;margin-top:18px}
.guide-chapter{min-width:0;scroll-margin-top:140px;border:1px solid var(--color-border);border-radius:17px;background:#fff;box-shadow:var(--shadow-card)}
summary{list-style:none;cursor:pointer}
summary::-webkit-details-marker{display:none}
.guide-chapter>summary{display:flex;min-width:0;align-items:center;gap:11px;padding:16px}
.guide-chapter__icon{display:grid;width:36px;height:36px;flex:none;place-items:center;border-radius:11px;background:var(--color-primary-soft)}
.guide-chapter__icon img{width:21px;height:21px}
.guide-chapter__title{display:block;min-width:0;flex:1}
.guide-chapter__title h2{margin-top:3px;font-size:17px;line-height:1.5}
.guide-chapter__title>span:last-child{display:block;margin-top:4px;color:var(--color-text-secondary);font-size:12px;line-height:1.6;overflow-wrap:anywhere}
.guide-chevron{flex:none;color:var(--color-text-secondary);font-size:20px;transition:transform .15s ease}
details[open]>summary>.guide-chevron{transform:rotate(180deg)}
.guide-chapter__body{min-width:0;padding:0 16px 16px;border-top:1px solid #edf2f1;overflow-wrap:anywhere}
.guide-scene{margin-top:14px;font-size:13px}
.guide-scene b{display:block;margin-bottom:4px;color:var(--color-text-primary);font-weight:650}
.guide-steps{display:grid;gap:18px;margin:20px 0;padding:0;list-style:none}
.guide-steps li{display:grid;min-width:0;grid-template-columns:24px minmax(0,1fr);gap:10px}
.guide-steps li>span{display:grid;width:24px;height:24px;place-items:center;border-radius:50%;background:#edf6f3;color:var(--color-primary-strong);font-size:12px;font-weight:750}
.guide-steps h3,.guide-result h3,.guide-notes h3{font-size:14px;font-weight:700;line-height:1.7}
.guide-steps p{margin-top:5px;font-size:14px;line-height:1.8}
.guide-result{padding:13px;border-radius:12px;background:#eaf8f1}
.guide-result h3{color:#22634e}
.guide-result p{margin-top:4px;color:#3e6e60;font-size:13px;line-height:1.75}
.guide-notes{margin-top:14px;padding:13px;border-radius:12px;background:#fff7e9}
.guide-notes h3{color:#805a21}
.guide-notes ul{display:grid;gap:8px;margin:7px 0 0;padding-left:18px;color:#766443;font-size:13px;line-height:1.75}
.guide-action{margin-top:16px;font-size:14px;white-space:normal}
.guide-top-link{display:block;width:fit-content;max-width:100%;margin:12px auto 0;padding:7px 4px;border:0;background:transparent;color:var(--color-primary-strong);font-size:13px;line-height:1.6;cursor:pointer}
#guide-directory-title{scroll-margin-top:140px}
.guide-empty{padding:24px 16px;border:1px dashed #b9d2cd;border-radius:15px;background:#fff;text-align:center}
.guide-empty h2{font-size:17px}
.guide-empty p{margin:10px 0 14px;font-size:13px}
.guide-faq{margin-top:26px}
.guide-faq details{margin-top:9px;border:1px solid var(--color-border);border-radius:13px;background:#fff}
.guide-faq summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px;font-size:14px;font-weight:650;line-height:1.6;overflow-wrap:anywhere}
.guide-faq details>div{padding:0 14px 14px}
.guide-faq p{font-size:14px;line-height:1.8}
.guide-faq .guide-top-link{margin-left:0}
.guide-footer{margin-top:28px;padding:20px 16px;border-radius:16px;background:#eaf4f1;text-align:center}
.guide-footer h2{font-size:17px}
.guide-footer p{margin:9px 0 14px;font-size:13px;line-height:1.75}
.guide-footer .button{font-size:14px}
@media(max-width:360px){.guide-intro{grid-template-columns:minmax(0,1fr) 70px;padding:18px 14px}.guide-intro h2{font-size:23px}.guide-flow button{padding:12px 9px;gap:7px}.guide-directory{grid-template-columns:minmax(0,1fr)}.guide-chapter>summary{padding:14px 12px;gap:8px}.guide-chapter__body{padding:0 12px 14px}.guide-chapter__icon{width:30px;height:30px}.guide-heading{align-items:flex-start}}
@media(prefers-reduced-motion:reduce){.guide-chevron{transition:none}}
</style>
