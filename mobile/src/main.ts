import {createApp} from 'vue';
import {createPinia} from 'pinia';
import {Capacitor} from '@capacitor/core';
import App from './App.vue';
import router from './router';
import '@ionic/vue/css/core.css';
import './style.css';
createApp(App).use(createPinia()).use(router).mount('#app');
// Native APK assets already work offline; a web cache must not pin old APK pages.
if('serviceWorker' in navigator){
  if(!Capacitor.isNativePlatform())navigator.serviceWorker.register('/sw.js').catch(()=>{});
  else navigator.serviceWorker.getRegistrations().then(registrations=>Promise.all(registrations.filter(item=>item.scope===location.origin+'/').map(item=>item.unregister()))).catch(()=>{});
}
