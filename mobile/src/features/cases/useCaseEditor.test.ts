import {createPinia, setActivePinia} from 'pinia';
import {effectScope, ref} from 'vue';
import {afterEach, expect, it, vi} from 'vitest';
import {api} from '../../core/http';
import {useCasesStore} from './store';
import {useCaseEditor} from './useCaseEditor';

vi.mock('../../core/http', () => ({api: vi.fn(), hasSession: () => true}));

function pendingPatch() {
  let resolve!: (value: {id: string; title: string}) => void;
  let reject!: (error: Error) => void;
  const response = new Promise<{id: string; title: string}>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return {response, resolve, reject};
}

afterEach(() => vi.resetAllMocks());

it.each(['success', 'failure'])('isolates a late A PATCH %s while B is saving', async outcome => {
  setActivePinia(createPinia());
  const cases = useCasesStore();
  cases.items = [{id: 'A', title: 'old A'}, {id: 'B', title: 'old B'}];
  cases.selected = cases.items[0];
  const caseId = ref('A'), error = ref('');
  const scope = effectScope();
  try {
    const editor = scope.run(() => useCaseEditor(caseId, error))!;
    const a = pendingPatch(), b = pendingPatch();
    vi.mocked(api).mockReturnValueOnce(a.response).mockReturnValueOnce(b.response);
    editor.beginEdit();
    editor.draft.value.title = 'new A';
    const saveA = editor.saveCase();
    expect(editor.saving.value).toBe(true);

    caseId.value = 'B';
    cases.selected = cases.items[1];
    expect(editor.editing.value).toBe(false);
    expect(editor.saving.value).toBe(false);
    editor.beginEdit();
    editor.draft.value.title = 'new B';
    const saveB = editor.saveCase();
    expect(api).toHaveBeenNthCalledWith(1, '/api/v1/cases/A', expect.objectContaining({method: 'PATCH'}));
    expect(api).toHaveBeenNthCalledWith(2, '/api/v1/cases/B', expect.objectContaining({method: 'PATCH'}));

    if (outcome === 'success') a.resolve({id: 'A', title: 'new A'});
    else a.reject(new Error('A save failed'));
    await saveA;
    expect(cases.items.map(item => item.title)).toEqual([outcome === 'success' ? 'new A' : 'old A', 'old B']);
    expect(cases.selected).toEqual({id: 'B', title: 'old B'});
    expect(editor.draft.value.title).toBe('new B');
    expect(editor.editing.value).toBe(true);
    expect(editor.saving.value).toBe(true);
    expect(editor.pageMessage.value).toBe('');
    expect(error.value).toBe('');

    if (outcome === 'success') {
      b.reject(new Error('B save failed'));
      await saveB;
      expect(error.value).toBe('B save failed');
      expect(editor.editing.value).toBe(true);
      expect(editor.pageMessage.value).toBe('');
    } else {
      b.resolve({id: 'B', title: 'new B'});
      await saveB;
      expect(cases.selected.title).toBe('new B');
      expect(cases.items[1].title).toBe('new B');
      expect(editor.editing.value).toBe(false);
      expect(editor.pageMessage.value).toBe('事项信息已保存。');
      expect(error.value).toBe('');
    }
    expect(editor.saving.value).toBe(false);
  } finally {
    scope.stop();
  }
});
