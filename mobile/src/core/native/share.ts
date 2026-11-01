import {Capacitor,registerPlugin,type PluginListenerHandle} from '@capacitor/core';
type SharedItem={id:string;kind?:'text'|'url'|'file';text?:string;local_path?:string;name?:string;mime?:string;state:string;error?:string};
interface PendingImportsPlugin {getPending():Promise<{items:SharedItem[]}>;clearPending(options?:{ids:string[]}):Promise<void>;addListener(eventName:'pendingImportsChanged',listener:()=>void):Promise<PluginListenerHandle>}
const native=registerPlugin<PendingImportsPlugin>('PendingImports');
export async function readShared(){if(!Capacitor.isNativePlatform())return [] as SharedItem[];return (await native.getPending()).items}
export async function takeSharedFiles(items:SharedItem[]){const files:File[]=[];for(const item of items){if(item.kind==='file'&&item.local_path&&item.state==='pending'){const response=await fetch(Capacitor.convertFileSrc(item.local_path));if(!response.ok)throw Error('分享文件暂不可读，请重新分享');const blob=await response.blob();files.push(new File([blob],item.name||'shared_file',{type:item.mime||blob.type}))}}return files}
export async function clearShared(ids?:string[]){if(Capacitor.isNativePlatform())await native.clearPending(ids?{ids}:undefined)}
export async function subscribeShared(listener:()=>void){if(!Capacitor.isNativePlatform())return {remove:async()=>{}};return native.addListener('pendingImportsChanged',listener)}
