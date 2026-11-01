import {describe,it,expect} from 'vitest';
import {inspectSources,requirePrivacyReview} from './privacyGuard';
describe('upload privacy guard',()=>{
 it('blocks without explicit confirmation before reading files',async()=>{
  let read=false;const file={name:'notice.txt',type:'text/plain',size:1,text:async()=>{read=true;return 'text'}} as File;
  await expect(requirePrivacyReview('',[file],'',false)).rejects.toThrow('明确确认');expect(read).toBe(false);
 });
 it('marks binary and URL contents as unscanned rather than safe',async()=>{
  const result=await inspectSources('电话13812345678',[{name:'scan.png',type:'image/png',size:10} as File],'https://example.com');
  expect(result.finding_types).toContain('手机号');expect(result.unchecked_sources).toEqual(['scan.png','网页内容及附件']);expect(result.requires_manual_review).toBe(true);
 });
 it('reads supported text files locally and blocks oversized inputs',async()=>{
  const file={name:'notice.txt',type:'text/plain',size:10,text:async()=> '13812345678'} as File;
  expect((await inspectSources('',[file])).finding_types).toContain('手机号');
  await expect(inspectSources('',[{name:'large.png',size:11*1024*1024} as File])).rejects.toThrow('格式限制');
 });
});
