import {defineStore} from 'pinia';
import {api,hasSession} from '../core/http';
import {useCasesStore} from '../features/cases/store';

export type DashboardData={
  date:string;
  timezone:string;
  total_cases:number;
  in_progress_cases:number;
  due_soon_cases:number;
  completed_cases:number;
  recent_cases:any[];
  today_tasks:any[];
};

export const useDashboardStore=defineStore('dashboard',{state:()=>({data:null as DashboardData|null,loading:false,error:''}),actions:{
  async load(){
    if(!hasSession()){this.data=null;this.error='';return null}
    this.loading=true;this.error='';this.data=null;
    try{const payload=await api('/api/v1/dashboard');payload.recent_cases?.forEach((item:any)=>item.relevance='UNKNOWN');this.data=payload;if(this.data)await useCasesStore().applyLocalRelevance(this.data.recent_cases);return this.data}
    catch(error:any){this.error=error.message||'首页数据读取失败';throw error}
    finally{this.loading=false}
  },
  async setTask(id:string,status:string){await api('/api/v1/tasks/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({status})});return this.load()},
}});
