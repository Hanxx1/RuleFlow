import {ref, watch, type Ref} from 'vue';
import {useCasesStore} from './store';

export function useCaseEditor(caseId: Readonly<Ref<string>>, pageError: Ref<string>) {
  const cases = useCasesStore();
  const editing = ref(false), saving = ref(false), pageMessage = ref('');
  const draft = ref({title: '', category: 'other', status: 'draft', deadline: ''});
  let saveVersion = 0;

  watch(caseId, () => {
    saveVersion++;
    editing.value = false;
    saving.value = false;
    pageMessage.value = '';
    pageError.value = '';
  }, {flush: 'sync'});

  function beginEdit() {
    const item = cases.selected;
    draft.value = {title: item.title, category: item.category, status: item.status, deadline: item.deadline?.slice(0, 10) || ''};
    editing.value = true;
    pageMessage.value = '';
  }

  async function saveCase() {
    const version = ++saveVersion;
    saving.value = true;
    pageError.value = '';
    try {
      await cases.updateCase(caseId.value, {...draft.value, deadline: draft.value.deadline || null});
      if (version !== saveVersion) return;
      editing.value = false;
      pageMessage.value = '事项信息已保存。';
    } catch (error) {
      if (version === saveVersion) pageError.value = (error as Error)?.message || '事项保存失败';
    } finally {
      if (version === saveVersion) saving.value = false;
    }
  }

  return {editing, saving, pageMessage, draft, beginEdit, saveCase};
}
