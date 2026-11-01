// Executes the shared semantic vectors against the actual ArkTS source after TypeScript transpilation.
// This checks rule semantics only; it is not a DevEco build or native-device verification.
import {createRequire} from 'node:module';
import {readFile,writeFile,mkdtemp,unlink,rmdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../mobile/package.json',import.meta.url));
const ts=require('typescript');
const source=await readFile(new URL('../harmony/entry/src/main/ets/common/RuleEngine.ets',import.meta.url),'utf8');
const schema=JSON.parse(await readFile(new URL('../shared/profile.schema.json',import.meta.url),'utf8'));
const declared=source.match(/const fields: string\[\] = \[([^\]]+)\]/)[1].split(',').map(item=>item.trim().replaceAll("'",''));
assert.deepEqual(declared.sort(),Object.keys(schema.properties).sort());
const vectors=JSON.parse(await readFile(new URL('../shared/test-vectors/rule-engine.json',import.meta.url),'utf8'));
const result=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022},reportDiagnostics:true});
assert.equal((result.diagnostics||[]).filter(item=>item.category===ts.DiagnosticCategory.Error).length,0);
const directory=await mkdtemp(join(tmpdir(),'zhishi-harmony-rules-')),file=join(directory,'rules.mjs');
try{
 await writeFile(file,result.outputText);
 const engine=await import(pathToFileURL(file).href);
 for(const vector of vectors)assert.equal(engine.evaluate(vector.ast,vector.profile),vector.value,vector.name);
 console.log(`PASS ${vectors.length} shared ArkTS-source semantic vectors; native SDK verification pending`);
}finally{await unlink(file);await rmdir(directory)}
