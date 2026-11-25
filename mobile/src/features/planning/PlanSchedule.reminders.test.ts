import {createSSRApp,defineComponent,h} from 'vue';
import {renderToString} from 'vue/server-renderer';
import {expect,it,vi} from 'vitest';
import PlanSchedule from './PlanSchedule.vue';
import {api} from '../../core/http';
import {saveReminder} from '../../core/native/reminders';

vi.mock('../../core/http',()=>({api:vi.fn(),ApiError:Error}));
vi.mock('../../core/native/reminders',()=>({
  androidReminders:true,isReminderEnabled:async()=>true,saveReminder:vi.fn()
}));
vi.mock('../../stores/account',()=>({useAccountStore:()=>({signedIn:true,user:{id:'account'}})}));
vi.mock('../cases/store',()=>({useCasesStore:()=>({})}));

it('saves edited schedule before requesting the reminder and shows both outcomes',async()=>{
  const item={id:'schedule',kind:'busy',title:'test',starts_at:'2030-05-12T10:00:00Z',ends_at:'2030-05-12T11:00:00Z'};
  const calls:string[]=[];
  vi.mocked(api).mockImplementation(async(_path,init)=>{
    if(init?.method==='PATCH'){calls.push('save');return item}
    return [];
  });
  vi.mocked(saveReminder).mockImplementation(async()=>{calls.push('remind');return '通知权限未开启，本次不会提醒。'});
  let page:any;
  await renderToString(createSSRApp(defineComponent({setup(){
    page=(PlanSchedule as any).setup({caseId:'',tasks:[]},{expose:()=>{}});
    return ()=>h('div');
  }})));
  await page.openEdit(item);
  await page.save();
  expect(calls).toEqual(['save','remind']);
  expect(saveReminder).toHaveBeenCalledWith('account',item,true,false);
  expect(page.message.value).toContain('安排已更新。通知权限未开启');
  expect(page.error.value).toBe('');
});
