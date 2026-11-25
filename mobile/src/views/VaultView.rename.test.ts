import {expect,it,vi} from 'vitest';
import {createSSRApp,defineComponent,h} from 'vue';
import {renderToString} from 'vue/server-renderer';
import VaultView from './VaultView.vue';
import {api} from '../core/http';

vi.mock('vue-router',()=>({useRoute:()=>({query:{}})}));
vi.mock('../stores/account',()=>({useAccountStore:()=>({signedIn:true})}));
vi.mock('../core/http',()=>({api:vi.fn()}));

it('reproduces the one-task payload after editing only the file name',async()=>{
  vi.mocked(api).mockImplementation(async(path,request)=>{
    if (path.endsWith('/plan')) return {ordered_tasks:[{id:'first'},{id:'second'}]};
    if (request?.method==='PATCH') return {};
    return [];
  });
  // Exercise the component handlers used by the edit and save buttons.
  let component:any;
  const app=createSSRApp(defineComponent({setup(){
    component=(VaultView as any).setup({}, {expose:()=>{}});
    return ()=>h('div');
  }}));
  await renderToString(app);
  await component.openEdit({id:'file',name:'old',category:'other',case_ids:['case'],task_ids:['first','second']});
  component.form.value.name='renamed';
  await component.save();
  const call=vi.mocked(api).mock.calls.find(([,init])=>init?.method==='PATCH');
  expect(call).toBeDefined();
  const payload=JSON.parse(call![1]!.body as string);
  expect(payload.name).toBe('renamed');
  expect(payload.task_ids).toEqual(['first']);
});
