import {computed,ref,type Ref} from 'vue';

// Page-local input protection only; never saves drafts or crosses account boundaries.
export function useCourseDraftGuard(current:()=>unknown,saving:Ref<boolean>,confirmDiscard:()=>boolean){
  const baseline=ref('');
  const dirty=computed(()=>baseline.value!==''&&JSON.stringify(current())!==baseline.value);
  function checkpoint(value:unknown=current()){baseline.value=JSON.stringify(value)}
  function canDiscard(){return !saving.value&&(!dirty.value||confirmDiscard())}
  function beforeUnload(event:BeforeUnloadEvent){
    if(dirty.value||saving.value){event.preventDefault();event.returnValue=''}
  }
  checkpoint();
  return {dirty,checkpoint,canDiscard,beforeUnload};
}
