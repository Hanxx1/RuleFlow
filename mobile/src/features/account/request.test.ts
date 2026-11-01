import {beforeEach, describe, expect, it, vi} from 'vitest';
const state = vi.hoisted(() => ({user: {id: 'first'}}));
vi.mock('../../stores/account', () => ({useAccountStore: () => state}));
vi.mock('../../core/http', () => ({api: vi.fn()}));
import {api} from '../../core/http';
import {accountApi} from './request';

describe('account request identity boundary', () => {
  beforeEach(() => { state.user = {id: 'first'}; vi.clearAllMocks(); });
  it('returns a response to the account that started the request', async () => {
    vi.mocked(api).mockResolvedValue({id: 'case-one'});
    await expect(accountApi('/api/v1/cases')).resolves.toEqual({id: 'case-one'});
  });
  it('rejects a late response after the account changes', async () => {
    let complete!: (value: unknown) => void;
    vi.mocked(api).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
    const pending = accountApi('/api/v1/cases');
    state.user = {id: 'second'};
    complete({id: 'private-first-account-case'});
    await expect(pending).rejects.toThrow('身份已变化');
  });
});
