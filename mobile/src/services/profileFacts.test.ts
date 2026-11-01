import {describe,it,expect} from 'vitest';
import {profilePayload,validFact} from './profileFacts';
describe('typed explicit profile facts',()=>{
 it('does not coerce numeric strings or booleans into years',()=>{
  expect(validFact('enrollment_year','2024')).toBe(false);expect(validFact('enrollment_year',true)).toBe(false);
  expect(()=>profilePayload({rank_percent:101})).toThrow('rank_percent');
  expect(()=>profilePayload({team_size:1.5})).toThrow('team_size');
 });
 it('preserves unknown nulls and known zero and normalizes form lists',()=>{
  expect(profilePayload({rank_percent:0,team_size:'',college:' 学院 ',moral_bonus_items:'志愿服务、竞赛'})).toEqual({facts:{rank_percent:0,team_size:null,college:'学院',moral_bonus_items:['志愿服务','竞赛']}});
 });
 it('rejects unsupported fields and does not return a partial valid request',()=>{
  expect(()=>profilePayload({enrollment_year:2024,unknown:1})).toThrow('unknown');
 });
});
