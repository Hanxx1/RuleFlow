import {beforeEach,expect,it,vi} from 'vitest';
import {createSSRApp,defineComponent,h} from 'vue';
import {renderToString} from 'vue/server-renderer';
import VaultView from './VaultView.vue';
import {api} from '../core/http';

vi.mock('vue-router',()=>({useRoute:()=>({query:{}})}));
vi.mock('../stores/account',()=>({useAccountStore:()=>({signedIn:true})}));
vi.mock('../core/http',()=>({api:vi.fn()}));

const linkedTwice={id:'file',name:'old',category:'other',case_ids:['case'],task_ids:['first','second']};

beforeEach(()=>{
  vi.resetAllMocks();
  vi.mocked(api).mockImplementation(async(path,request)=>{
    if(path.endsWith('/plan'))return {ordered_tasks:[{id:'first'},{id:'second'}]};
    return request?.method==='PATCH'?{}:[];
  });
});

async function edit(item:typeof linkedTwice,changes:Record<string,string>){
  // Exercise the same handlers as the mobile editor.
  let component:any;
  const app=createSSRApp(defineComponent({setup(){
    component=(VaultView as any).setup({}, {expose:()=>{}});
    return ()=>h('div');
  }}));
  await renderToString(app);
  await component.openEdit(item);
  Object.assign(component.form.value,changes);
  await component.save();
  const patch=vi.mocked(api).mock.calls.find(([,init])=>init?.method==='PATCH');
  return patch && JSON.parse(patch[1]!.body as string);
}

it('renames a file without sending its multiple task associations',async()=>{
  expect(await edit(linkedTwice,{name:'renamed'})).toEqual({name:'renamed'});
});

it('edits category independently even when there are multiple Case associations',async()=>{
  expect(await edit({...linkedTwice,case_ids:['case','other-case'],task_ids:[]},{category:'proof'}))
    .toEqual({category:'proof'});
});

it('only replaces associations after an explicit edit of a single selection',async()=>{
  const single={...linkedTwice,task_ids:['first']};
  expect(await edit(single,{task_id:'second'})).toEqual({case_ids:['case'],task_ids:['second']});
});

it('sends nothing when the editor is saved without changes',async()=>{
  expect(await edit(linkedTwice,{})).toBeUndefined();
});
