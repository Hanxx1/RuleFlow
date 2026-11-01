import {defineStore} from 'pinia';
import {api} from '../services/api';
import type {ImportBatch} from '../types/product';

const activeKey='zhishi-active-import-batch';
function savedBatch(){return typeof localStorage==='undefined'?'':localStorage.getItem(activeKey)||''}

export const useImportBatchStore=defineStore('import-batch',{state:()=>({data:null as ImportBatch|null,activeBatchId:savedBatch(),loading:false,error:''}),actions:{
  remember(id:string){this.activeBatchId=id;if(typeof localStorage!=='undefined')localStorage.setItem(activeKey,id)},
  clearActive(){this.activeBatchId='';if(typeof localStorage!=='undefined')localStorage.removeItem(activeKey)},
  async create(title?:string){const batch=await api('/api/v1/import-batches',{method:'POST',body:JSON.stringify({title:title||undefined})}) as ImportBatch;this.data=batch;this.remember(batch.id);return batch},
  async load(id:string){if(this.data?.id!==id)this.data=null;this.loading=true;this.error='';try{this.data=await api('/api/v1/import-batches/'+encodeURIComponent(id));this.remember(id);return this.data}catch(error:any){this.error=error.message;throw error}finally{this.loading=false}},
  async saveSources(targetId:string|undefined,draft:{title:string;text:string;url:string;files:File[]}){
    this.loading=true;this.error='';
    try{
      const batchId=targetId||(await this.create(draft.title.trim()||undefined)).id;this.remember(batchId);
      if(draft.text.trim())await api(`/api/v1/import-batches/${batchId}/sources/text`,{method:'POST',body:JSON.stringify({text:draft.text.trim(),title:draft.title.trim()||undefined,consent:true})});
      if(draft.url.trim())await api(`/api/v1/import-batches/${batchId}/sources/url`,{method:'POST',body:JSON.stringify({url:draft.url.trim(),title:draft.title.trim()||undefined,consent:true,include_attachments:true})});
      if(draft.files.length){const form=new FormData();draft.files.forEach(file=>form.append('files',file));form.append('consent','true');await api(`/api/v1/import-batches/${batchId}/sources/files`,{method:'POST',body:form})}
      return await this.load(batchId);
    }catch(error:any){this.error=error.message;throw error}finally{this.loading=false}
  },
  async removeSource(batchId:string,sourceId:string){await api(`/api/v1/import-batches/${batchId}/sources/${sourceId}`,{method:'DELETE'});return this.load(batchId)},
  async analyze(batchId:string){this.loading=true;this.error='';try{this.data=await api(`/api/v1/import-batches/${batchId}/analyze`,{method:'POST'});this.remember(batchId);return this.data}catch(error:any){this.error=error.message;throw error}finally{this.loading=false}},
}});
