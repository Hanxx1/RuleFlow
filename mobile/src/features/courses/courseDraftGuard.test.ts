import {describe,it,expect,vi} from 'vitest';
import {ref} from 'vue';
import {useCourseDraftGuard} from './courseDraftGuard';

function setup(){
  const input=ref({name:'原课程',requirement:'原要求',custom:''}),saving=ref(false);
  const confirm=vi.fn(()=>false);
  return {input,saving,confirm,guard:useCourseDraftGuard(()=>input.value,saving,confirm)};
}
describe('course unsaved input protection',()=>{
  it('allows untouched and reverted inputs without prompting',()=>{
    const {input,guard,confirm}=setup();
    expect(guard.canDiscard()).toBe(true);
    input.value.name='修改课程';expect(guard.dirty.value).toBe(true);
    input.value.name='原课程';expect(guard.canDiscard()).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
  });
  it.each(['name','requirement','custom'] as const)('keeps %s input when leaving is declined',key=>{
    const {input,guard,confirm}=setup();input.value[key]='未保存输入';
    expect(guard.canDiscard()).toBe(false);expect(input.value[key]).toBe('未保存输入');
    expect(guard.dirty.value).toBe(true);expect(confirm).toHaveBeenCalledOnce();
    confirm.mockReturnValue(true);expect(guard.canDiscard()).toBe(true);
    expect(guard.dirty.value).toBe(true); // Permission alone must not erase input.
  });
  it('protects input across a failed save and clears only after explicit success checkpoint',()=>{
    const {input,saving,guard,confirm}=setup();input.value.requirement='待保存';saving.value=true;
    expect(guard.canDiscard()).toBe(false);expect(confirm).not.toHaveBeenCalled();
    saving.value=false;expect(guard.canDiscard()).toBe(false);
    guard.checkpoint();expect(guard.canDiscard()).toBe(true);
  });
  it('retains an unsubmitted custom field after a requirement save',()=>{
    const {input,guard}=setup();input.value.custom='待添加字段';input.value.requirement='已保存要求';
    guard.checkpoint({...input.value,custom:''});expect(guard.dirty.value).toBe(true);
    input.value.custom='';expect(guard.dirty.value).toBe(false);
  });
  it('warns on reload for dirty input or an in-flight save, but not for a clean page',()=>{
    const {input,saving,guard}=setup();
    const event={preventDefault:vi.fn(),returnValue:undefined} as unknown as BeforeUnloadEvent;
    guard.beforeUnload(event);expect(event.preventDefault).not.toHaveBeenCalled();
    input.value.name='未保存';guard.beforeUnload(event);
    expect(event.preventDefault).toHaveBeenCalledOnce();expect(event.returnValue).toBe('');
    guard.checkpoint();saving.value=true;guard.beforeUnload(event);
    expect(event.preventDefault).toHaveBeenCalledTimes(2);
  });
  it('resets to the new identity without carrying a previous account draft',()=>{
    const {input,guard,confirm}=setup();input.value.name='前一账户输入';
    input.value={name:'',requirement:'',custom:''};guard.checkpoint();
    expect(guard.canDiscard()).toBe(true);expect(confirm).not.toHaveBeenCalled();
  });
});
