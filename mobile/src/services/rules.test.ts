import {describe,it,expect} from 'vitest';import {evaluate} from './rules';import vectors from '../../../shared/test-vectors/rule-engine.json';describe('shared vectors',()=>{for(const v of vectors as any[])it(v.name,()=>expect(evaluate(v.ast,v.profile)).toBe(v.value))});
describe('AST structure boundary',()=>{
 it('rejects unsupported fields, injected properties and malformed evidence',()=>{
  expect(()=>evaluate({op:'eq',field:'profile.unknown',value:1},{})).toThrow();
  expect(()=>evaluate({op:'exists',field:'profile.role',script:'run'},{})).toThrow();
  expect(()=>evaluate({op:'exists',field:'profile.role',evidence:'block:one'},{})).toThrow();
 });
});
