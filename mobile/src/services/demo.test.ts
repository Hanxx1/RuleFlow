import {afterEach,describe,expect,it,vi} from 'vitest';
import {loadDemo,loadPublicDemos} from './demo';

const fixtures:Record<string,unknown>={
 'notice.json':{id:'demo',title:'离线示例',deadline:'2026-09-30'},
 'blocks.json':[
  {id:'rule-ref',source_name:'模拟规则',text:'本科生适用',confidence:1},
  {id:'item-ref',source_name:'模拟通知',text:'准备并提交申请表',confidence:1},
 ],
 'rules.json':[
  {id:'scope',ast:{op:'and',args:[{op:'in',field:'profile.student_type',value:['undergraduate'],evidence:['rule-ref']}]}},
  {id:'bonus',ast:{op:'exists',field:'profile.moral_bonus_items',evidence:['rule-ref']}},
 ],
 'tasks.json':{nodes:[{id:'task',title:'准备申请表',evidence:['item-ref']}],edges:[]},
 'materials.json':[{id:'material',title:'申请表',evidence_ids:['item-ref']}],
 'facts.json':[{id:'fact',key:'学生类型',value:'本科生（演示）'}],
 'schedule.json':[{id:'schedule',title:'填写申请表',day_index:1,start_time:'14:00',end_time:'15:00',evidence_ids:['item-ref']}],
};

function mockFixtures(overrides:Record<string,unknown>={}){
 const values={...fixtures,...overrides};
 vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request)=>{
  const name=String(input).split('/').pop()||'';
  return new Response(JSON.stringify(values[name]),{status:values[name]?200:404,headers:{'Content-Type':'application/json'}});
 }));
}

describe('offline demo bundle',()=>{
 afterEach(()=>vi.unstubAllGlobals());

 it('isolates public sample identifiers and rejects ungrounded tasks',async()=>{
  mockFixtures({'public-cases.json':[{id:'demo-public-test',blocks:[{id:'ref'}],tasks:{nodes:[{id:'t',evidence_ids:['ref']}]},materials:[]}]});
  expect(await loadPublicDemos()).toHaveLength(1);
  mockFixtures({'public-cases.json':[{id:'demo-public-test',blocks:[],tasks:{nodes:[{id:'t',evidence_ids:['ref']}]},materials:[]}]});
  await expect(loadPublicDemos()).rejects.toThrow('公开演示任务缺少有效 EvidenceRef');
 });

 it('loads schedule, materials and facts with normalized task EvidenceRefs',async()=>{
  mockFixtures();
  const demo=await loadDemo({student_type:'undergraduate',enrollment_year:2024});
  expect(demo.schedule).toHaveLength(1);
  expect(demo.materials).toHaveLength(1);
  expect(demo.facts).toHaveLength(1);
  expect(demo.tasks.nodes[0].evidence_ids).toEqual(['item-ref']);
 });

 it('rejects a schedule item whose EvidenceRef is missing',async()=>{
  mockFixtures({'schedule.json':[{id:'schedule',title:'无依据日程',evidence_ids:['missing-ref']}]});
  await expect(loadDemo({student_type:'undergraduate'})).rejects.toThrow('演示日程缺少有效 EvidenceRef');
 });
});
