import type {MixedCandidate,MixedReview} from './mixedReviewModel';
export function createMixedReviewSamples():MixedReview {
  const item=(id:string,kind:MixedCandidate['kind'],title:string,content:string,sourceId:string,quote:string,target:string):MixedCandidate=>({id,kind,title,content,sourceId,quote,target,operation:'create',selected:false,acknowledged:false,eligibility:'UNKNOWN',missingFields:['适用对象尚未人工核对'],dependsOn:[],version:1,attempts:0,status:'pending',message:''});
  return {
    courses:[{id:'sample-linear',name:'线性代数',term:'2026 秋季'},{id:'sample-code',name:'程序设计',term:'2026 秋季'},{id:'sample-linear-spring',name:'线性代数',term:'2027 春季'}],
    sources:[{id:'sample-line-1',text:'【合成通知】线性代数本周作业：完成第3章练习。'},{id:'sample-line-2',text:'【合成通知】程序设计实验要求改为提交实验报告，先核对新要求，再准备报告。'},{id:'sample-line-3',text:'【合成通知】校园摄影活动开放报名，资格条件待核对。'}],
    items:[
      {...item('sample-linear-task','task','线性代数第3章练习','完成第3章练习','sample-line-1','完成第3章练习','sample-linear'),existing:{target:'sample-linear',title:'已有第3章练习任务（合成）',value:'尚未完成；可能与本次通知重复'}},
      {...item('sample-code-rule','requirement','程序设计实验要求','提交实验报告','sample-line-2','程序设计实验要求改为提交实验报告','sample-code'),operation:'update',existing:{target:'sample-code',title:'当前实验要求（合成）',value:'旧记录：课堂验收，无需提交报告'}},
      {...item('sample-code-task','task','准备程序设计实验报告','准备实验报告','sample-line-2','先核对新要求，再准备报告','sample-code'),dependsOn:['sample-code-rule']},
      item('sample-campus','case','校园摄影活动','核对摄影活动报名条件','sample-line-3','校园摄影活动开放报名，资格条件待核对','campus'),
      item('sample-knowledge','knowledge','课程资料关联建议','关联老师课件','missing-source','课件由两门课程共享','sample-linear'),
    ],
  };
}
