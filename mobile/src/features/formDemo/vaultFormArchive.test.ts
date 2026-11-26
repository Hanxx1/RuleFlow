import {beforeEach,describe,expect,it,vi} from 'vitest'
import {api,ApiError} from '../../core/http'
import {officeMime} from './officeDelivery'
import {prepareVaultFormArchive,VaultArchiveUncertain} from './vaultFormArchive'

vi.mock('../../core/http',async(importOriginal)=>({
  ...await importOriginal<typeof import('../../core/http')>(),api:vi.fn(),
}))
const filename = '申请表.docx'
const mime = officeMime('docx')
const artifact = {filename,blob:new Blob(['exact exported contents'],{type:mime})}
const response = {id:'item-a',name:filename,mime,category:'form',size:artifact.blob.size,case_ids:[],task_ids:[]}

beforeEach(()=>vi.resetAllMocks())

describe('archive a verified form to the owner’s Vault',()=>{
  it('requires consent and manually confirms the unscanned Office file without a network request',async()=>{
    const review = vi.fn(()=>false)
    await expect(prepareVaultFormArchive(artifact,undefined,false,review)).rejects.toThrow('明确确认')
    expect(review).not.toHaveBeenCalled()
    await expect(prepareVaultFormArchive(artifact,undefined,true,review)).resolves.toBeUndefined()
    expect(review).toHaveBeenCalledTimes(1)
    expect(api).not.toHaveBeenCalled()
  })

  it('uploads the exact bytes with explicit case scope only and no automatic POST retry',async()=>{
    const submit = await prepareVaultFormArchive(artifact,'case-a',true,()=>true)
    expect(api).not.toHaveBeenCalled()
    vi.mocked(api).mockResolvedValueOnce({...response,case_ids:['case-a']})
    expect(await submit!()).toEqual({id:'item-a',linkedCase:true})
    const [[url,options,retry]] = vi.mocked(api).mock.calls
    expect([url,options?.method,retry]).toEqual(['/api/v1/vault/items','POST',false])
    const body = options?.body as FormData
    expect(body.get('name')).toBe(filename)
    expect(body.get('category')).toBe('form')
    expect(body.get('consent')).toBe('true')
    expect(body.get('case_ids')).toBe('["case-a"]')
    expect(body.get('task_ids')).toBe('[]')
    const file = body.get('file') as File
    expect([file.name,file.type,await file.text()]).toEqual([filename,mime,await artifact.blob.text()])
  })

  it('permits unlinked files, rejects invalid receipts, and reports missing acknowledgement as uncertain',async()=>{
    const submit = (await prepareVaultFormArchive(artifact,undefined,true,()=>true))!
    vi.mocked(api).mockResolvedValueOnce(response)
    await expect(submit()).resolves.toEqual({id:'item-a',linkedCase:false})
    expect((vi.mocked(api).mock.calls[0][1]?.body as FormData).get('case_ids')).toBe('[]')
    vi.mocked(api).mockResolvedValueOnce({...response,size:1})
    await expect(submit()).rejects.toBeInstanceOf(VaultArchiveUncertain)
    vi.mocked(api).mockRejectedValueOnce(new TypeError('response lost'))
    await expect(submit()).rejects.toBeInstanceOf(VaultArchiveUncertain)
    vi.mocked(api).mockRejectedValueOnce(new ApiError('not saved',undefined,422))
    await expect(submit()).rejects.toThrow('not saved')
    expect(api).toHaveBeenCalledTimes(4)
  })
})
