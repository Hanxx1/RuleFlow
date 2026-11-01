import {api} from '../core/http';

export type PrivacyPreview={redacted:string,count:number,types:string[]}
export type PrivacyFinding={id:string;type:'id_card'|'phone'|'bank_card'|'email'|'student_id'|'name'|'address';label:string;start:number;end:number;original:string;redacted:string}
export type PrivacyAnalysis={findings:PrivacyFinding[];redacted_text:string;unsupported_types:string[];offset_unit:string;engine_version:string;persisted:false}
export const analyzePrivacy=(text:string):Promise<PrivacyAnalysis>=>api('/api/v1/privacy/analyze',{method:'POST',body:JSON.stringify({text})});
export function redact(text:string):PrivacyPreview { let count=0; const types:string[]=[]; const use=(rx:RegExp,label:string,fn:(m:string)=>string)=>{text=text.replace(rx,m=>{count++;if(!types.includes(label))types.push(label);return fn(m)})}; use(/(?<!\d)\d{17}[\dXx](?!\d)/g,'身份证号',m=>'*'.repeat(m.length)); text=text.replace(/(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)/g,(_,a,b)=>{count++;if(!types.includes('手机号'))types.push('手机号');return `${a}****${b}`}); use(/(?<!\d)\d{16,19}(?!\d)/g,'银行卡号',m=>'*'.repeat(m.length)); for(const [rx,label] of [[/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'邮箱'],[/(?<!\d)\d{8,12}(?!\d)/g,'疑似学号']] as const){if(rx.test(text)){if(!types.includes(label))types.push(label);rx.lastIndex=0}} return {redacted:text,count,types} }
