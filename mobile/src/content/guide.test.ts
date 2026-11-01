import {describe,expect,it} from 'vitest';
import {guideChapters,guideFaqs,guideTopic,searchGuide} from './guide';

describe('guide search and chapter selection',()=>{
  it('shows the full guide for an empty or whitespace query',()=>{
    expect(searchGuide('  ').chapters).toHaveLength(guideChapters.length);
    expect(searchGuide('').faqs).toHaveLength(guideFaqs.length);
  });
  it('searches detailed instructions and normalizes full width text and case',()=>{
    const result=searchGuide('ｐｄｆ ２０');
    expect(result.chapters.map(chapter=>chapter.id)).toContain('import');
    expect(result.chapters.map(chapter=>chapter.id)).not.toContain('privacy');
  });
  it('finds troubleshooting answers independently of chapter matches',()=>{
    const result=searchGuide('127.0.0.1');
    expect(result.faqs.map(faq=>faq.id)).toEqual(['connection']);
    expect(result.chapters).toEqual([]);
  });
  it('matches terminology used on the analysis screen',()=>{
    expect(searchGuide('unknown').chapters.map(chapter=>chapter.id)).toContain('analysis');
    expect(searchGuide('未安排').chapters.map(chapter=>chapter.id)).toContain('plan');
  });
  it('supports a genuinely empty result without silently showing unrelated instructions',()=>{
    expect(searchGuide('完全没有匹配的查询词98765')).toEqual({chapters:[],faqs:[]});
  });
  it('only accepts known single chapter IDs for contextual navigation',()=>{
    expect(guideTopic('analysis')).toBe('analysis');
    expect(guideTopic('unknown')).toBeUndefined();
    expect(guideTopic(['analysis','privacy'])).toBeUndefined();
    expect(guideTopic(undefined)).toBeUndefined();
  });
});
