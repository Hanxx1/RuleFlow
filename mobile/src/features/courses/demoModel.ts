// Synthetic, memory-only examples; never seed account storage.
export * from './courseModel';
import {createCourse,type CoursePreview} from './courseModel';
export function createSamples():CoursePreview[] {
  const current=createCourse('sample-current','软件工程','2026 秋季');
  current.teacher='示例教师';current.location='示例教学楼 201';current.group='合成小组：小林（整理资料）、小周（演示）；关联作业待接入';
  current.requirements[0]={...current.requirements[0],state:'已确认',value:'课堂签到，以教师后续通知为准。',source:'合成教师说明第 1 行（仅用于交互演示）'};
  current.requirements[1]={...current.requirements[1],state:'待核对',value:'评分比例尚待教师说明。',source:'合成课程介绍第 2 行（未确认）'};
  current.requirements[2]={...current.requirements[2],state:'明确无要求',source:'合成教师说明第 3 行：本课程无实验要求'};
  return [current,createCourse('sample-previous','软件工程','2026 春季'),createCourse('sample-math','高等数学','2026 秋季')];
}
