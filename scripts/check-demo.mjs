import {readFile} from 'node:fs/promises';
const files=['blocks','facts','materials','notice','rules','schedule','tasks','public-cases'];
for(const name of files){
  const source=new URL(`../shared/demo/${name==='public-cases'?'':'assessment_2024/'}${name}.json`,import.meta.url);
  const target=new URL(`../mobile/public/demo/${name}.json`,import.meta.url);
  if(!(await readFile(source)).equals(await readFile(target)))throw Error(`Demo copy differs: ${name}.json`);
}
console.log(`PASS ${files.length} demo copies match shared sources`);
