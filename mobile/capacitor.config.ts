import type { CapacitorConfig } from '@capacitor/cli';
const config: CapacitorConfig = { appId:'com.zhishi.ruleflow', appName:'知事 RuleFlow', webDir:'web-dist', server:{androidScheme:process.env.VITE_API_BASE?.startsWith('http://')?'http':'https'} };
export default config;
