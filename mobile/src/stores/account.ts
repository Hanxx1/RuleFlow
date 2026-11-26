import {indexedWorkspace} from '../services/clientWorkspace';
import {clearExperiences} from '../features/experience/archive';
import {clearOwnerFormDrafts} from '../features/formDemo/savedDraftSession';
import {defineStore} from 'pinia';import {api,auth,clearSession} from '../core/http';
export type AccountUser={id:string;email:string};
export const useAccountStore=defineStore('account',{state:()=>({user:null as AccountUser|null,formDraftEpoch:null as number|null,loading:false,error:'',devices:[] as any[],settings:null as any,completeness:null as any}),getters:{signedIn:s=>!!s.user},actions:{
  async login(email:string,password:string){
    this.loading=true;this.error=''
    try{
      const d=await auth.login(email,password)
      // Each authenticated tab captures its own generation before opening any form.
      this.formDraftEpoch=await import('../features/formDemo/savedFormDrafts')
        .then(({openDraftSession})=>openDraftSession(d.user.id)).catch(()=>null)
      try{clearOwnerFormDrafts(d.user.id)}catch{/* Legacy tab storage is no longer read. */}
      this.user=d.user
      return d
    }catch(e:any){this.error=e.message;throw e}
    finally{this.loading=false}
  },
  async loadDevices(){this.devices=await auth.sessions()},async revokeDevice(id:string){await auth.revokeSession(id);this.devices=this.devices.filter(item=>item.id!==id)},async loadSettings(){this.settings=await api('/api/v1/account/settings');return this.settings},async saveSettings(value:any){this.settings=await api('/api/v1/account/settings',{method:'PATCH',body:JSON.stringify(value)});return this.settings},async loadCompleteness(){this.completeness=await api('/api/v1/profile/completeness');return this.completeness},
  async logout(){
    const owner=this.user?.id
    this.formDraftEpoch=null
    const revokeDrafts=owner && import('../features/formDemo/savedFormDrafts')
      .then(({revokeDraftSessions})=>revokeDraftSessions(owner))
    const [drafts,remote]=await Promise.allSettled([revokeDrafts,auth.logout()])
    try{
      this.user=null
      if(owner){
        try{clearOwnerFormDrafts(owner)}
        finally{
          try{await indexedWorkspace.remove(owner)}
          finally{await clearExperiences(owner)}
        }
      }
      if(drafts.status==='rejected') throw Error('本机草稿未能确认清理，请检查浏览器存储后重新登录并退出。')
      if(remote.status==='rejected') throw Error('本机已退出，服务端会话暂未确认退出，请核对网络。')
    }
    finally{
      clearSession();this.user=null;this.devices=[];this.settings=null;this.completeness=null
      window.dispatchEvent(new Event('zhishi-client-changed'))
    }
  }
}});
