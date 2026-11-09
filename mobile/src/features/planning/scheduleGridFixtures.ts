import type {GridItem} from './scheduleGrid';
export const anchorDay='2026-11-09';
export const fixtureEvidence:Record<string,string>={'fixture:cm005:input':'固定样例输入：课程、任务及忙碌时间均为人工构造，仅用于网格验收，不是官方通知或账户数据。'};
export const fixtureCourses:Record<string,string>={'fixture:course:linear':'线性代数（样例）· 2026秋季；本样例含周一与周三两条时段。'};
const make=(id:string,title:string,kind:GridItem['kind'],start:string,end:string,courseId?:string):GridItem=>({id,title,kind,starts_at:start+':00+08:00',ends_at:end+':00+08:00',evidence_ids:['fixture:cm005:input'],courseId});
export const gridFixtures:GridItem[]=[
 make('K1-A','线性代数（样例）','course','2026-11-09T09:00','2026-11-09T10:00','fixture:course:linear'),
 make('K1-B','线性代数（样例）','course','2026-11-11T14:00','2026-11-11T15:30','fixture:course:linear'),
 make('T1','整理课堂笔记','task','2026-11-09T09:30','2026-11-09T10:30'),
 make('B1','小组讨论','busy','2026-11-09T09:45','2026-11-09T10:15'),
 make('T2','复习例题','task','2026-11-09T10:30','2026-11-09T11:00'),
 make('B2','跨日观测（样例）','busy','2026-11-10T23:30','2026-11-11T00:30'),
 make('B3','午夜结束（样例）','busy','2026-11-12T23:00','2026-11-13T00:00'),
 make('T3','用十分钟核对本周所有线性代数练习中的易错步骤（长标题样例）','task','2026-11-14T12:05','2026-11-14T12:15'),
 make('B4','跨周观测（样例）','busy','2026-11-15T23:30','2026-11-16T00:30'),
];
export const exceptionalFixtures:GridItem[]=[
 {...make('offset','UTC等价时刻','task','2026-11-09T09:00','2026-11-09T10:00'),starts_at:'2026-11-09T01:00:00Z',ends_at:'2026-11-09T02:00:00Z'},
 {...make('missing','缺少依据的样例','busy','2026-11-09T11:00','2026-11-09T12:00'),evidence_ids:[]},
 make('reversed','反向时间','task','2026-11-09T12:00','2026-11-09T11:00'),
 make('zero','零长度时间','task','2026-11-09T13:00','2026-11-09T13:00'),
 {...make('invalid','非法时间','task','2026-11-09T12:00','2026-11-09T13:00'),starts_at:'invalid'},
];
