import {api} from '../../core/http';
import {useAccountStore} from '../../stores/account';

export async function accountApi(path:string,init:RequestInit={}){const owner=useAccountStore().user?.id||'offline';const value=await api(path,init);if(owner!==(useAccountStore().user?.id||'offline'))throw Error('身份已变化，请重新读取事项');return value}
