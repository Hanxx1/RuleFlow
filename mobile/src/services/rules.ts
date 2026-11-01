import schema from '../../../shared/rule_ast.schema.json';
import {validFact} from './profileFacts';
export type Truth='TRUE'|'FALSE'|'UNKNOWN';
const fields=new Set<string>(schema.$defs.field.enum);
const operators=new Set<string>((schema.oneOf as any[]).flatMap(variant=>variant.properties.op.enum||[variant.properties.op.const]));
export function evaluate(ast:any,p:Record<string,any>,depth=0):Truth {
 const op=ast?.op;if(depth>32||!operators.has(op))throw Error('invalid AST');
 const allowed=['and','or','not'].includes(op)?['op','args','evidence']:['op','field','value','evidence'];
 if(Object.keys(ast).some(key=>!allowed.includes(key)))throw Error('invalid AST properties');
 if(ast.evidence!==undefined&&(!Array.isArray(ast.evidence)||ast.evidence.some((ref:any)=>typeof ref!=='string'||!/^block:[A-Za-z0-9._:-]+$/.test(ref))))throw Error('invalid EvidenceRef');
 if(['and','or','not'].includes(op)){
  const args=ast.args;if(!Array.isArray(args)||!args.length||(op==='not'&&args.length!==1))throw Error('invalid AST');
  const values=args.map((child:any)=>evaluate(child,p,depth+1));
  return op==='not'?(values[0]==='TRUE'?'FALSE':values[0]==='FALSE'?'TRUE':'UNKNOWN'):op==='and'?(values.includes('FALSE')?'FALSE':values.every((x:Truth)=>x==='TRUE')?'TRUE':'UNKNOWN'):(values.includes('TRUE')?'TRUE':values.every((x:Truth)=>x==='FALSE')?'FALSE':'UNKNOWN');
 }
 if(!fields.has(ast.field))throw Error('invalid AST field');
 const key=ast.field.replace('profile.',''),actual=p[key],expected=ast.value;
 if(actual===undefined||actual===null||actual===''||!validFact(key,actual))return 'UNKNOWN';
 if(op==='exists')return 'TRUE';
 if(op==='in'){
  if(Array.isArray(actual)||!Array.isArray(expected)||!expected.length||expected.some(item=>item===null||!validFact(key,item)))return 'UNKNOWN';
  return expected.includes(actual)?'TRUE':'FALSE';
 }
 if(op==='contains'){
  if(typeof expected!=='string'||(!Array.isArray(actual)&&typeof actual!=='string'))return 'UNKNOWN';
  return actual.includes(expected)?'TRUE':'FALSE';
 }
 if(expected===null||!validFact(key,expected))return 'UNKNOWN';
 if(['gte','lte','before','after'].includes(op)&&typeof actual!=='number')return 'UNKNOWN';
 const ok=op==='eq'?JSON.stringify(actual)===JSON.stringify(expected):op==='gte'?actual>=expected:op==='lte'?actual<=expected:op==='before'?actual<expected:actual>expected;
 return ok?'TRUE':'FALSE';
}
