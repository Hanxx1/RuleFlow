import {describe,it,expect} from 'vitest';
import {emptyWorkspace,formAssertions,parseSupplement,resolvedFacts,validateWorkspace,loadWorkspace,exportWorkspace} from './clientWorkspace';
describe('client facts',()=>{
 it('keeps supplement candidates unconfirmed and ignores negation',()=>{const rows=parseSupplement('我是本科生。德育成绩85。不是我是研究生');expect(rows).toHaveLength(2);expect(rows.every(a=>!a.confirmed)).toBe(true)});
 it('retains contradictions and scoped/expired assertions as unknown',()=>{const w=emptyWorkspace('a');w.assertions=[...formAssertions({team_size:3}),...formAssertions({team_size:5}),...formAssertions({rank_percent:10},'case-x','2020-01-01')];expect(resolvedFacts(w,'case-x','2026-10-14').facts).toEqual({});expect(resolvedFacts(w).conflicts).toEqual(['team_size'])});
 it('does not import another account backup or unsupported fields',()=>{const w=emptyWorkspace('a');expect(()=>validateWorkspace(w,'b')).toThrow();expect(()=>formAssertions({eval:'code'})).toThrow();expect(exportWorkspace(w)).not.toContain('token')});
 it('migrates v1 without sharing owner data',async()=>{const storage={read:async()=>({...emptyWorkspace('a'),version:1}),write:async()=>{},remove:async()=>{}};expect((await loadWorkspace('a',storage)).version).toBe(3);await expect(loadWorkspace('b',storage)).rejects.toThrow()});
});
