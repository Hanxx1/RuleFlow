import {describe,expect,it} from 'vitest';
import {createSSRApp,h} from 'vue';
import {renderToString} from '@vue/server-renderer';
import {createMemoryHistory,createRouter,RouterView} from 'vue-router';
import GuideView from './GuideView.vue';
import GuideLink from '../components/GuideLink.vue';

function makeRouter(){
  return createRouter({history:createMemoryHistory(),routes:[
    {path:'/guide',component:GuideView},
    ...['/home','/me','/help','/imports/new','/cases','/profile','/plan','/timetable','/vault','/knowledge','/privacy','/cases/:id/analysis'].map(path=>({path,component:{render:()=>null}})),
  ]});
}
async function renderGuide(location:string){
  const router=makeRouter();
  await router.push(location);await router.isReady();
  return renderToString(createSSRApp({render:()=>h(RouterView)}).use(router));
}
function returnAnchor(html:string){return html.match(/<a[^>]*aria-label="返回原页面"[^>]*>/)?.[0]||''}

describe('guide screen',()=>{
  it('renders the full guide without a backend or account session',async()=>{
    const html=await renderGuide('/guide');
    expect(html).toContain('第一次用，按这四步');
    expect(html).toContain('导入一份通知');
    expect(html).toContain('确认整份排程');
    expect(html).toContain('打开离线样例');
    expect(html).toContain('搜索指南');
    expect(html.match(/class="guide-chapter"/g)).toHaveLength(8);
    expect(returnAnchor(html)).toContain('href="/home"');
  });
  it('opens the requested chapter and preserves the original page and its query',async()=>{
    const html=await renderGuide('/guide?topic=analysis&from='+encodeURIComponent('/imports/new?batch=batch-one'));
    expect(html).toMatch(/<details[^>]*id="guide-analysis"[^>]*\sopen[\s>]/);
    expect(returnAnchor(html)).toContain('href="/imports/new?batch=batch-one"');
  });
  it('falls back to the import chapter for a stale chapter ID',async()=>{
    const html=await renderGuide('/guide?topic=removed-chapter');
    expect(html).toMatch(/<details[^>]*id="guide-import"[^>]*\sopen[\s>]/);
  });
  it.each(['https://example.com','//example.com','javascript:alert(1)','/guide'])('keeps the return link inside the app for %s',async from=>{
    const html=await renderGuide('/guide?from='+encodeURIComponent(from));
    expect(returnAnchor(html)).toContain('href="/home"');
  });
  it('retains case context when opening help from the analysis page',async()=>{
    const router=makeRouter();
    const source='/cases/case-one/analysis?view=review';
    await router.push(source);await router.isReady();
    const html=await renderToString(createSSRApp({render:()=>h(GuideLink,{topic:'analysis'})}).use(router));
    const expected=router.resolve({path:'/guide',query:{topic:'analysis',from:source}}).href.replace(/&/g,'&amp;');
    expect(html).toContain(`href="${expected}"`);
  });
});
