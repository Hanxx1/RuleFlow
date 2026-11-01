import {afterEach,describe,expect,it,vi} from 'vitest';
import {api,apiBlob,ApiError,checkApiHealth} from './http';

describe('API connectivity diagnostics',()=>{
 afterEach(()=>vi.unstubAllGlobals());
 it('preserves document preview error codes and readable messages',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:{code:'DOCUMENT_CONTENT_MISSING',message:'原件不可用'}}),{status:404})));
  const error=await apiBlob('/api/v1/documents/test/pages/1').catch(value=>value);
  expect(error).toBeInstanceOf(ApiError);expect(error.code).toBe('DOCUMENT_CONTENT_MISSING');expect(error.message).toBe('原件不可用');
 });
 it('accepts a healthy backend response',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({status:'ok'}),{status:200,headers:{'Content-Type':'application/json'}})));
  await expect(checkApiHealth()).resolves.toEqual({status:'ok'});
 });
 it('turns a network failure into an actionable message',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(checkApiHealth()).rejects.toThrow('VITE_API_BASE');
 });
 it('preserves structured URL failure codes with a readable message',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:{code:'url_dns_failed',message:'网址 DNS 解析失败'}}),{status:502,headers:{'Content-Type':'application/json'}})));
  const error=await api('/api/v1/imports/url',{method:'POST'}).catch(value=>value);
  expect(error).toBeInstanceOf(ApiError);expect(error.code).toBe('url_dns_failed');expect(error.message).toBe('网址 DNS 解析失败');
 });
});
