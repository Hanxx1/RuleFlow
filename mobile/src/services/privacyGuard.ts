import {redact} from './privacy';
export async function inspectSources(text:string,files:File[],url=''){
 const findingTypes=new Set(redact(text).types),unchecked:string[]=[];
 for(const file of files){
  const limit=/\.(png|jpe?g)$/i.test(file.name)?10:20;
  if(file.size>limit*1024*1024)throw Error(`文件超过格式限制：${file.name}`);
  if(file.type==='text/plain'||/\.txt$/i.test(file.name)){for(const type of redact(await file.text()).types)findingTypes.add(type)}
  else unchecked.push(file.name);
 }
 if(url)unchecked.push('网页内容及附件');
 return {finding_types:[...findingTypes],unchecked_sources:unchecked,requires_manual_review:true,scope:'local_text_checks_only'};
}
export async function requirePrivacyReview(text:string,files:File[],url:string,confirmed:boolean){
 if(!confirmed)throw Error('请先核对隐私处理范围并明确确认上传。');
 return inspectSources(text,files,url);
}
