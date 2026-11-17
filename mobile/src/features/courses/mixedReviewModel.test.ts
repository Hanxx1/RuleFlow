import {describe,it,expect} from 'vitest';
import {allowedOperations,editMixedItem,resolveSampleReceipt,reviewIssue,simulateMixedReview,type MixedReview} from './mixedReviewModel';
import {createMixedReviewSamples} from './mixedReviewSamples';

const get=(r:MixedReview,id:string)=>r.items.find(item=>item.id===id)!;
const selected=(ids:string[])=>{let r=createMixedReviewSamples();for(const id of ids)r=editMixedItem(r,id,{selected:true,acknowledged:true});return r};
describe('CM-007 synthetic review coordination',()=>{
  it('creates isolated unselected samples and retains UNKNOWN and missing fields',()=>{
    const a=createMixedReviewSamples(),b=createMixedReviewSamples();a.items[0].selected=true;
    expect(b.items.every(item=>!item.selected&&item.status==='pending')).toBe(true);
    expect(b.items.every(item=>item.eligibility==='UNKNOWN'&&item.missingFields.length)).toBe(true);
    expect(new Set(b.courses.map(course=>course.id)).size).toBe(3);
  });
  it('an empty selection performs no operations and never means select all',()=>{
    const r=createMixedReviewSamples();expect(simulateMixedReview(r,[],'partial')).toEqual(r);
    expect(simulateMixedReview(r,r.items.map(item=>item.id),'partial')).toEqual(r);
  });
  it('allows two independent course and campus decisions without changing the input',()=>{
    const ids=['sample-linear-task','sample-campus'],r=selected(ids),before=JSON.stringify(r);
    const out=simulateMixedReview(r,ids,'partial');expect(ids.map(id=>get(out,id).status)).toEqual(['success','success']);
    expect(get(out,'sample-code-rule').attempts).toBe(0);expect(JSON.stringify(r)).toBe(before);
    expect(out.items.every(item=>item.eligibility==='UNKNOWN')).toBe(true);
  });
  it('requires explicit conflict/duplicate review and does not silently apply changes',()=>{
    const r=editMixedItem(createMixedReviewSamples(),'sample-linear-task',{selected:true});
    expect(reviewIssue(r,r.items[0])).toContain('现有记录');
    const out=simulateMixedReview(r,['sample-linear-task'],'partial');expect(out.items[0]).toMatchObject({status:'blocked',attempts:0});
    expect(out.items[0].existing?.value).toBe(r.items[0].existing?.value);
  });
  it('source absence or a forged quote blocks execution even when selected',()=>{
    const r=selected(['sample-knowledge','sample-campus']);get(r,'sample-campus').quote='原文不存在的句子';
    const out=simulateMixedReview(r,['sample-knowledge','sample-campus'],'partial');
    for(const id of ['sample-knowledge','sample-campus'])expect(get(out,id)).toMatchObject({status:'blocked',attempts:0});
  });
  it('changing target resets confirmation, disallows old links, and keeps cross-term identity distinct',()=>{
    let r=selected(['sample-linear-task']);r=editMixedItem(r,'sample-linear-task',{operation:'link'});
    expect(get(r,'sample-linear-task').acknowledged).toBe(false);
    r=editMixedItem(r,'sample-linear-task',{acknowledged:true});r=editMixedItem(r,'sample-linear-task',{target:'sample-linear-spring'});
    expect(get(r,'sample-linear-task')).toMatchObject({target:'sample-linear-spring',operation:'create',acknowledged:false,version:3});
    expect(allowedOperations(get(r,'sample-linear-task'))).not.toContain('link');
    expect(get(r,'sample-code-task').target).toBe('sample-code');
  });
  it('content editing invalidates prior acknowledgement and preserves the original quote',()=>{
    const r=selected(['sample-code-rule']),old=get(r,'sample-code-rule');
    const out=editMixedItem(r,old.id,{content:'用户整理的新要求'});
    expect(get(out,old.id)).toMatchObject({content:'用户整理的新要求',quote:old.quote,acknowledged:false,version:2});
    expect(reviewIssue(out,get(out,old.id))).toContain('核对');
  });
  it('processes selected prerequisites before dependents even when input order is reversed',()=>{
    const ids=['sample-code-task','sample-code-rule'],r=selected(ids);r.items.reverse();
    const out=simulateMixedReview(r,ids,'partial');expect(get(out,ids[1]).status).toBe('success');expect(get(out,ids[0]).status).toBe('failed');
  });
  it('waits when a prerequisite is unselected and resumes after that prerequisite succeeds',()=>{
    let r=selected(['sample-code-task']);r=simulateMixedReview(r,['sample-code-task'],'partial');
    expect(get(r,'sample-code-task')).toMatchObject({status:'blocked',attempts:0});
    r=editMixedItem(r,'sample-code-rule',{selected:true,acknowledged:true});r=simulateMixedReview(r,['sample-code-rule'],'partial');
    r=simulateMixedReview(r,['sample-code-task'],'partial');expect(get(r,'sample-code-task')).toMatchObject({status:'failed',attempts:1});
  });
  it('blocks mismatched, missing or cyclic prerequisites without manufacturing execution',()=>{
    const r=selected(['sample-code-task','sample-code-rule']);get(r,'sample-code-rule').target='sample-linear';
    expect(get(simulateMixedReview(r,['sample-code-task'],'partial'),'sample-code-task')).toMatchObject({status:'blocked',attempts:0});
    get(r,'sample-code-task').dependsOn=['missing'];expect(reviewIssue(r,get(r,'sample-code-task'))).toContain('归属');
    get(r,'sample-code-task').dependsOn=['sample-code-task'];
    expect(get(simulateMixedReview(r,['sample-code-task'],'partial'),'sample-code-task').attempts).toBe(0);
  });
  it('retrying only a failed item leaves successful decisions and their attempts unchanged',()=>{
    const ids=['sample-code-rule','sample-code-task','sample-campus'];let r=selected(ids);r=simulateMixedReview(r,ids,'partial');
    const before=get(r,'sample-code-rule');expect(get(r,'sample-code-task').status).toBe('failed');
    r=simulateMixedReview(r,['sample-code-task'],'partial');expect(get(r,'sample-code-task')).toMatchObject({status:'success',attempts:2});
    expect(get(r,'sample-code-rule')).toEqual(before);r=simulateMixedReview(r,ids,'partial');expect(get(r,'sample-campus').attempts).toBe(1);
  });
  it('unknown outcomes cannot be blindly retried or edited; receipt query does not execute again',()=>{
    const ids=['sample-code-rule','sample-code-task'];let r=simulateMixedReview(selected(ids),ids,'unknown');
    expect(get(r,ids[1])).toMatchObject({status:'unknown',attempts:1});
    r=simulateMixedReview(r,ids,'unknown');expect(get(r,ids[1]).attempts).toBe(1);
    expect(()=>editMixedItem(r,ids[1],{content:'不得覆盖'})).toThrow('结果未知');
    r=resolveSampleReceipt(r,ids[1]);expect(get(r,ids[1])).toMatchObject({status:'success',attempts:1});
    expect(()=>editMixedItem(r,ids[1],{target:'sample-linear'})).toThrow();
    expect(()=>resolveSampleReceipt(r,ids[1])).toThrow('没有');
  });
  it('ignore does not execute even a source-invalid suggestion or count as prerequisite success',()=>{
    let r=selected(['sample-knowledge','sample-code-rule','sample-code-task']);
    r=editMixedItem(r,'sample-knowledge',{operation:'ignore'});r=editMixedItem(r,'sample-code-rule',{operation:'ignore'});
    r=simulateMixedReview(r,r.items.map(item=>item.id),'partial');expect(get(r,'sample-knowledge')).toMatchObject({status:'ignored',attempts:0});expect(get(r,'sample-code-task')).toMatchObject({status:'blocked',attempts:0});
  });
  it('refuses invalid targets, operations, blank/oversized input and stale selections',()=>{
    const r=selected(['sample-campus']);get(r,'sample-campus').target='sample-linear';expect(reviewIssue(r,get(r,'sample-campus'))).toContain('归属');
    get(r,'sample-campus').target='campus';get(r,'sample-campus').operation='link';expect(reviewIssue(r,get(r,'sample-campus'))).toContain('对应记录');
    get(r,'sample-campus').operation='create';get(r,'sample-campus').content='';expect(reviewIssue(r,get(r,'sample-campus'))).toContain('内容');
    get(r,'sample-campus').content='字'.repeat(2001);expect(reviewIssue(r,get(r,'sample-campus'))).toContain('2000');
    expect(()=>simulateMixedReview(r,['missing'],'partial')).toThrow('无效');expect(()=>simulateMixedReview(r,['sample-campus','sample-campus'],'partial')).toThrow('无效');
  });
});
