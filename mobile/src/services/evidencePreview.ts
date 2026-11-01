import {apiBlob} from '../core/http';
export function boundingBox(evidence:any){
 const box=evidence?.bbox,width=Number(evidence?.page_width),height=Number(evidence?.page_height);
 if(!Array.isArray(box)||!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return null;
 const xs=box.length===4&&typeof box[0]==='number'?[box[0],box[2]]:box.map((point:any)=>point?.[0]);
 const ys=box.length===4&&typeof box[0]==='number'?[box[1],box[3]]:box.map((point:any)=>point?.[1]);
 if(!xs.length||!ys.length||![...xs,...ys].every(Number.isFinite))return null;
 const left=Math.max(0,Math.min(...xs)),top=Math.max(0,Math.min(...ys)),right=Math.min(width,Math.max(...xs)),bottom=Math.min(height,Math.max(...ys));
 if(right<=left||bottom<=top)return null;
 return {left:`${100*left/width}%`,top:`${100*top/height}%`,width:`${100*(right-left)/width}%`,height:`${100*(bottom-top)/height}%`};
}
export const loadEvidencePreview=(evidence:any)=>apiBlob(`/api/v1/documents/${encodeURIComponent(evidence.document_id)}/pages/${evidence.page||1}`);
