// C-side real TCP check. Uses only synthetic accounts/files in a fresh temporary root.
// Run: node scripts/test-form-original-client.mjs <python-with-server-dependencies>
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {mkdtemp,readFile,writeFile,unlink,rm} from 'node:fs/promises';
import {createRequire} from 'node:module';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=process.argv[2]||process.env.CAMPUSWEAVE_TEST_PYTHON;
if(!python)throw Error('Pass a Python executable with the server requirements installed.');
const temporaryRoot=await mkdtemp(path.join(os.tmpdir(),'campusweave-original-'));
const listener=net.createServer();listener.listen(0,'127.0.0.1');await once(listener,'listening');
const port=listener.address().port;await new Promise(resolve=>listener.close(resolve));
const base=`http://127.0.0.1:${port}`;
const server=spawn(python,['-m','uvicorn','app.main:app','--app-dir','server','--host','127.0.0.1','--port',String(port),'--no-access-log'],{
  cwd:root,windowsHide:true,stdio:'ignore',env:{...process.env,
    DATABASE_PATH:path.join(temporaryRoot,'test.sqlite'),DEMO_DATABASE_PATH:path.join(temporaryRoot,'demo.sqlite'),
    APP_ENV:'development',DEMO_MODE:'false',REFRESH_TOKEN_PEPPER:'synthetic-original-client-test',
    LLM_BASE_URL:'',LLM_MODEL:'',LLM_API_KEY:'',
    VAULT_UPLOAD_ROOT:path.join(temporaryRoot,'vault'),DEMO_UPLOAD_ROOT:path.join(temporaryRoot,'demo'),
    DOCUMENT_UPLOAD_ROOT:path.join(temporaryRoot,'documents'),DEMO_DOCUMENT_ROOT:path.join(temporaryRoot,'demo-documents')},
});
let launchError;server.on('error',error=>{launchError=error});
let vite;
try{
  let ready=false;
  for(let attempt=0;attempt<100;attempt++){
    if(launchError)throw launchError;
    if(server.exitCode!==null)throw Error(`Isolated backend exited (${server.exitCode}).`);
    try{ready=(await fetch(base+'/health',{signal:AbortSignal.timeout(500)})).ok}catch{}
    if(ready)break;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert(ready,'Isolated backend did not become healthy.');
  process.env.VITE_API_BASE=base;
  const require=createRequire(path.join(root,'mobile','package.json'));
  const {createServer}=require('vite');
  vite=await createServer({root:path.join(root,'mobile'),configFile:false,server:{middlewareMode:true},appType:'custom'});
  const transport=await vite.ssrLoadModule('/src/core/http.ts');
  const {readFormContext}=await vite.ssrLoadModule('/src/features/imports/formContext.ts');
  const {readFormOriginal}=await vite.ssrLoadModule('/src/features/imports/formOriginal.ts');
  async function call(url,method='GET',body,token){
    const response=await fetch(base+url,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),
      ...(token?{Authorization:'Bearer '+token}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(10000)});
    assert(response.ok,`Synthetic setup request failed (${response.status}).`);
    return (await response.json()).data;
  }
  async function account(email){
    const password='synthetic original test password';
    const created=await call('/api/v1/auth/register','POST',{email,password});
    await call('/api/v1/auth/verify','POST',{token:created.development_verification_token});
    return call('/api/v1/auth/login','POST',{email,password});
  }
  const owner=await account('original-owner@example.com'),other=await account('original-other@example.com');
  transport.setSession(owner.access_token,owner.refresh_token);
  const batch=await call('/api/v1/import-batches','POST',{},owner.access_token);
  const batchPath='/api/v1/import-batches/'+batch.id;
  const files=new FormData();files.set('consent','true');
  const originals=['Synthetic form A\n00001234','Synthetic form B\n00005678'];
  for(const text of originals)files.append('files',new Blob([text],{type:'text/plain'}),'same-name.txt');
  const upload=await fetch(base+batchPath+'/sources/files',{method:'POST',headers:{Authorization:'Bearer '+owner.access_token},body:files});
  assert(upload.ok,'Synthetic upload failed.');await upload.json();
  const current=await call(batchPath,'GET',undefined,owner.access_token);
  const context=await readFormContext(batch.id,current.revision);
  assert.equal(context.sources.length,2);assert.notEqual(context.sources[0].source_id,context.sources[1].source_id);
  const downloaded=[];
  for(const source of context.sources)downloaded.push(await (await readFormOriginal(context,source.source_id)).text());
  assert.deepEqual(downloaded.sort(),[...originals].sort());
  console.log('PASS same-named sources retain identity; actual TCP downloads match original bytes.');
  transport.setSession(other.access_token,other.refresh_token);
  await assert.rejects(readFormOriginal(context,context.sources[0].source_id),error=>error.status===404);
  transport.setSession(owner.access_token,owner.refresh_token);
  console.log('PASS foreign account rejected through the actual client and backend.');
  const first=context.sources[0];
  // Locate only this script's synthetic original by its server-issued document ID.
  const {readdir}=await import('node:fs/promises');
  const documents=path.join(temporaryRoot,'documents');
  const owners=await readdir(documents);assert.equal(owners.length,1);
  const originalPath=path.join(documents,owners[0],first.document_ref.id);
  assert(path.resolve(originalPath).startsWith(path.resolve(temporaryRoot)+path.sep));
  const saved=await readFile(originalPath),tampered=Buffer.from(saved);tampered[0]^=1;
  try{
    await writeFile(originalPath,tampered);
    await assert.rejects(readFormOriginal(context,first.source_id),error=>error.code==='SOURCE_ORIGINAL_MISMATCH');
  }finally{await writeFile(originalPath,saved)}
  console.log('PASS same-size file tampering rejected by actual SHA-256 verification.');
  await unlink(originalPath);
  const missing=await readFormContext(batch.id,current.revision);
  assert(missing.sources.find(source=>source.source_id===first.source_id).lines.length>0);
  await assert.rejects(readFormOriginal(context,first.source_id),error=>error.code==='SOURCE_ORIGINAL_UNAVAILABLE');
  console.log('PASS missing original rejected while historical source lines remain readable.');
  await call(batchPath+'/sources/text','POST',{text:'Synthetic added notice',consent:true},owner.access_token);
  await assert.rejects(readFormOriginal(context,context.sources[1].source_id),error=>error.code==='IMPORT_BATCH_STALE');
  console.log('PASS stale snapshot rejected before original delivery.');
}finally{
  // Stop the processes started here before removing this script's unique temporary tree.
  try{if(vite)await vite.close()}finally{
    if(server.pid&&server.exitCode===null){const exited=once(server,'exit');server.kill();await exited}
    if(path.dirname(temporaryRoot)===path.resolve(os.tmpdir())&&path.basename(temporaryRoot).startsWith('campusweave-original-')){
      await rm(temporaryRoot,{recursive:true,force:true,maxRetries:3,retryDelay:200});
    }
  }
}
