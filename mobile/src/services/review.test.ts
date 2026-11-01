import {describe,it,expect,vi,afterEach} from 'vitest';
import {confirmationPayload,loadReview,submitReview,type AnalysisReview} from './review';
const review:AnalysisReview={revision:3,status:'needs_confirmation',candidate:{actions:[{id:'action:0',title:'填写申请表',evidence_ids:['block:one'],evidence_quotes:{'block:one':'请填写申请表'}}],dates:[]},decision:null};
const selection={actionIds:['action:0'],deadlineId:'',manualDeadline:'',noDeadline:true,consent:true};
describe('analysis review contract',()=>{
 afterEach(()=>vi.unstubAllGlobals());
 it('requires explicit confirmation and an exclusive date choice',()=>{
  expect(()=>confirmationPayload(review,{...selection,consent:false})).toThrow('明确确认');
  expect(()=>confirmationPayload(review,{...selection,manualDeadline:'2026-10-25'})).toThrow('一种');
  expect(()=>confirmationPayload(review,{...selection,actionIds:['foreign']})).toThrow('变化');
 });
 it('carries the revision and selected action IDs without modifying candidates',()=>{
  expect(confirmationPayload(review,selection)).toEqual({revision:3,action_ids:['action:0'],deadline_id:null,manual_deadline:null,no_deadline:true,consent:true});
  expect(review.status).toBe('needs_confirmation');
 });
 it('handles an empty review envelope',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({data:null}))));
  expect(await loadReview('legacy')).toBeNull();
 });
 it('surfaces a stale revision error without claiming confirmation',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:{code:'REVIEW_STALE',message:'请重新读取候选'}}),{status:409})));
  await expect(submitReview('case',review,selection)).rejects.toThrow('重新读取');
  expect(review.status).toBe('needs_confirmation');
 });
});
