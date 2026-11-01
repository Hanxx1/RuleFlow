import {createRouter,createWebHistory,type RouteRecordRaw} from 'vue-router';
import Page from './views/Page.vue';
import HomeView from './views/HomeView.vue';
import CasesView from './views/CasesView.vue';
import PlanView from './views/PlanView.vue';
import MeView from './views/MeView.vue';

const utilityPages=[
  ['/welcome','欢迎'],['/auth/login','登录'],['/auth/register','注册'],['/auth/verify','验证邮箱'],['/auth/reset','重置密码'],
  ['/imports/:id/review','分析结果确认'],
  ['/cases/new','手动新建'],['/cases/:id/questions','补充信息'],
  ['/cases/:id/materials','材料'],['/cases/:id/flow','流程'],['/cases/:id/sources','来源'],['/cases/:id/conflicts','冲突复核'],
  ['/inbox','消息'],['/settings/privacy','隐私设置'],
  ['/settings/notifications','通知设置'],['/help','帮助与反馈'],['/about','关于知事'],
] as const;
const routes:RouteRecordRaw[]=[
  {path:'/',redirect:'/welcome'},
  {path:'/home',component:HomeView,meta:{title:'工作台'}},
  {path:'/cases',component:CasesView,meta:{title:'我的事项'}},
  {path:'/plan/schedule',redirect:{path:'/plan',query:{tab:'schedule'}}},
  {path:'/plan',component:PlanView,meta:{title:'执行计划'}},
  {path:'/me',component:MeView,meta:{title:'我的'}},
  {path:'/guide',component:()=>import('./views/GuideView.vue'),meta:{title:'使用指南'}},
  {path:'/profile',component:()=>import('./views/ClientProfileView.vue'),meta:{title:'个人画像'}},
  {path:'/timetable',component:()=>import('./views/TimetableView.vue'),meta:{title:'本机课表'}},
  {path:'/settings/devices',component:()=>import('./views/DevicesView.vue'),meta:{title:'登录设备'}},
  {path:'/settings/account',component:()=>import('./views/AccountSettingsView.vue'),meta:{title:'账户设置'}},
  {path:'/vault',component:()=>import('./views/VaultView.vue'),meta:{title:'材料库'}},
  {path:'/knowledge',component:()=>import('./views/KnowledgeLibraryView.vue'),meta:{title:'知识资料库'}},
  {path:'/documents/:id/privacy',component:()=>import('./views/DocumentPrivacyView.vue'),meta:{title:'文件隐私与脱敏'}},
  {path:'/privacy',component:()=>import('./views/SafeShareView.vue'),meta:{title:'隐私保护'}},
  {path:'/imports/new',component:()=>import('./views/ImportView.vue'),meta:{title:'导入通知'}},
  {path:'/imports/sources',component:()=>import('./views/ImportSourcesView.vue'),meta:{title:'确认导入来源'}},
  {path:'/imports/:id/sources',component:()=>import('./views/ImportSourcesView.vue'),meta:{title:'确认导入来源'}},
  {path:'/imports/:id/progress',component:()=>import('./views/ImportProgressView.vue'),meta:{title:'分析进度'}},
  {path:'/cases/:id/analysis',component:()=>import('./views/AnalysisResultView.vue'),meta:{title:'解析结果'}},
  {path:'/cases/:id/relevance',component:()=>import('./views/RelevanceView.vue'),meta:{title:'相关性判断'}},
  {path:'/cases/:id/knowledge',component:()=>import('./views/KnowledgeEvidenceView.vue'),meta:{title:'规则依据'}},
  {path:'/cases/:id/rules',component:()=>import('./views/KnowledgeEvidenceView.vue'),meta:{title:'规则依据'}},
  {path:'/cases/:id/schedule',redirect:to=>({path:'/plan',query:{tab:'schedule',case:String(to.params.id)}})},
  {path:'/cases/:id/privacy',redirect:to=>({path:'/privacy',query:{case:String(to.params.id)}})},
  {path:'/cases/:id',component:()=>import('./views/AnalysisResultView.vue'),meta:{title:'事项概览'}},
  ...utilityPages.map(([path,title])=>({path,component:Page,meta:{title}})),
];
export default createRouter({history:createWebHistory(),routes});
