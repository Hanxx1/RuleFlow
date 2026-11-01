import {computed,ref} from 'vue';
import {defineStore} from 'pinia';
import type {ImportDraftSource} from '../../types/product';

export const useImportDraftStore=defineStore('import-draft',()=>{
  const title=ref('');
  const text=ref('');
  const url=ref('');
  const files=ref<File[]>([]);
  const cameFromShare=ref(false);

  const sources=computed<ImportDraftSource[]>(()=>{
    const result:ImportDraftSource[]=[];
    if(text.value.trim())result.push({id:'text',kind:'text',label:cameFromShare.value?'分享文字':'粘贴文字',detail:`${text.value.trim().length} 个字符`});
    if(url.value.trim())result.push({id:'url',kind:'url',label:'网页链接',detail:url.value.trim()});
    files.value.forEach((file,index)=>result.push({id:`file-${index}`,kind:'file',label:file.name,detail:formatBytes(file.size),file}));
    return result;
  });
  const sourceKinds=computed(()=>new Set(sources.value.map(item=>item.kind)));

  function remove(id:string){
    if(id==='text'){text.value='';cameFromShare.value=false}
    else if(id==='url')url.value='';
    else if(id.startsWith('file-'))files.value.splice(Number(id.slice(5)),1);
  }
  function reset(){title.value='';text.value='';url.value='';files.value=[];cameFromShare.value=false}
  return {title,text,url,files,cameFromShare,sources,sourceKinds,remove,reset};
});

function formatBytes(value:number){
  if(value<1024)return `${value} B`;
  if(value<1024*1024)return `${(value/1024).toFixed(1)} KB`;
  return `${(value/1024/1024).toFixed(1)} MB`;
}
