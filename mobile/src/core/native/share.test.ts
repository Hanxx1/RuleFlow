import {beforeEach,describe,expect,it,vi} from 'vitest';
const mock=vi.hoisted(()=>({isNative:vi.fn(),getPending:vi.fn(),clearPending:vi.fn(),addListener:vi.fn(),convertFileSrc:vi.fn()}));
vi.mock('@capacitor/core',()=>({Capacitor:{isNativePlatform:mock.isNative,convertFileSrc:mock.convertFileSrc},registerPlugin:()=>mock}));
import {readShared,clearShared,subscribeShared,takeSharedFiles} from './share';
describe('Native share boundary',()=>{
 beforeEach(()=>{vi.clearAllMocks();mock.isNative.mockReturnValue(true);vi.unstubAllGlobals()});
 it('does not call native APIs on web',async()=>{mock.isNative.mockReturnValue(false);expect(await readShared()).toEqual([]);await clearShared();await subscribeShared(()=>{});expect(mock.getPending).not.toHaveBeenCalled();expect(mock.addListener).not.toHaveBeenCalled()});
 it('clears only the submitted snapshot IDs',async()=>{await clearShared(['one']);expect(mock.clearPending).toHaveBeenCalledWith({ids:['one']})});
 it('subscribes to later shares without uploading content',async()=>{const listener=()=>{};const remove=vi.fn();mock.addListener.mockResolvedValue({remove});const handle=await subscribeShared(listener);expect(mock.addListener).toHaveBeenCalledWith('pendingImportsChanged',listener);await handle.remove();expect(remove).toHaveBeenCalled()});
 it('rejects an unreadable cached file instead of uploading an error response',async()=>{mock.convertFileSrc.mockReturnValue('http://localhost/_capacitor_file_/cache');vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('missing',{status:404})));await expect(takeSharedFiles([{id:'one',kind:'file',local_path:'/private/cache',state:'pending'}])).rejects.toThrow('分享文件暂不可读')});
});
