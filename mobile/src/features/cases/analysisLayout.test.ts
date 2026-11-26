import {describe,it,expect,vi} from 'vitest';
import {createSSRApp,h} from 'vue';
import {renderToString} from '@vue/server-renderer';
import {createPinia} from 'pinia';
import {createRouter,createMemoryHistory} from 'vue-router';
import AnalysisResultView from './AnalysisResultView.vue';
import {useCasesStore} from './store';
import {useAccountStore} from '../../stores/account';
vi.mock('../../core/http',()=>({api:vi.fn(async()=>[]),hasSession:()=>false}));
// The sheet uses DOM focus/scroll locking, exercised by the browser check.
vi.mock('../../components/EvidenceBottomSheet.vue',()=>({default:{render:()=>null}}));

async function render({signedIn=false,missing=0,tasks=[] as any[]}={}){
 const pinia=createPinia(),router=createRouter({history:createMemoryHistory(),routes:[{path:'/cases/:id/analysis',component:AnalysisResultView},{path:'/:pathMatch(.*)*',component:{render:()=>null}}]});
 await router.push('/cases/test-case/analysis');await router.isReady();
 const cases=useCasesStore(pinia);cases.selected={id:'test-case',title:'合成通知',status:'review'};
 cases.resources={analysis:{questions:['核对适用条件','核对适用条件'],review_reasons:['尚未核对年份'],summary:'分析说明'},attachments:{missing_count:missing,items:[]},rules:[],evidence:[],tasks,materials:[],files:[]};
 if(signedIn)useAccountStore(pinia).user={id:'synthetic',email:'test@example.invalid'};
 return renderToString(createSSRApp({render:()=>h(AnalysisResultView)}).use(pinia).use(router));
}
describe('UX-A04 result hierarchy',()=>{
 it('puts notice and review before supporting panels; deduplicates identical questions',async()=>{
  const html=await render({signedIn:true});
  expect(html.indexOf('核对通知')).toBeLessThan(html.indexOf('核对日期与行动'));
  expect(html.indexOf('id="analysis-review"')).toBeLessThan(html.indexOf('附件完整度'));
  expect(html.match(/核对适用条件/g)).toHaveLength(1);
  expect(html).not.toContain('product-hero');
  expect(html).toContain('href="#analysis-review"');
  expect(html).not.toMatch(/<details[^>]*\sopen[\s>]/);
 });
 it('keeps incomplete attachment warning before confirmation and risk reasons outside details',async()=>{
  const html=await render({signedIn:true,missing:2});
  expect(html).toContain('还缺 2 项附件或读取失败');
  expect(html.indexOf('role="alert"')).toBeLessThan(html.indexOf('id="analysis-review"'));
  expect(html.indexOf('尚未核对年份')).toBeLessThan(html.indexOf('>分析说明</summary>'));
 });
 it('keeps the current case flow reachable for a signed-in user with zero tasks',async()=>{
  const html=await render({signedIn:true,tasks:[]});
  expect(html).toContain('尚未生成有证据支撑的执行步骤。');
  expect(html).toMatch(/<a\b[^>]*href="\/cases\/test-case\/flow"[^>]*>打开完整执行流程/);
 });
 it('retains existing tasks, evidence controls and navigation for offline reading',async()=>{
  const html=await render({tasks:[{id:'task',title:'提交申请',evidence_ids:['e1']}]});
  expect(html).toContain('提交申请');expect(html).toContain('打开完整执行流程');
  expect(html).toContain('href="/cases/test-case/sources"');
  expect(html).toContain('打开材料库');expect(html).toContain('规则依据');
  expect(html).not.toContain('id="analysis-review"');
 });
});
