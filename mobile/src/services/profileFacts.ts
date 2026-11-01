import schema from '../../../shared/profile.schema.json';
export function validFact(key:string,value:any):boolean{
 const spec=(schema.properties as Record<string,any>)[key];if(!spec)return false;if(value===null)return true;
 if(spec.type.includes('integer')){if(typeof value!=='number'||!Number.isInteger(value))return false}
 else if(spec.type.includes('number')){if(typeof value!=='number'||!Number.isFinite(value))return false}
 else if(spec.type.includes('string')){if(typeof value!=='string'||!value.trim()||value.length>(spec.maxLength||100))return false}
 else if(spec.type.includes('array')){if(!Array.isArray(value)||value.length>spec.maxItems||value.some(item=>typeof item!=='string'||!item.trim()||item.length>100)||new Set(value).size!==value.length)return false}
 if(spec.enum&&!spec.enum.includes(value))return false;
 if(spec.minimum!==undefined&&value<spec.minimum||spec.maximum!==undefined&&value>spec.maximum)return false;
 return true;
}
export function profilePayload(profile:Record<string,any>){
 const facts=Object.fromEntries(Object.entries(profile).map(([key,value])=>[key,key==='moral_bonus_items'&&typeof value==='string'?value.split(/[、,，]/).map(item=>item.trim()).filter(Boolean):value===''?null:typeof value==='string'?value.trim():value]));
 const invalid=Object.keys(facts).filter(key=>!validFact(key,facts[key]));
 if(invalid.length)throw Error('画像字段格式或范围无效，请核对：'+invalid.join('、'));
 return {facts};
}
