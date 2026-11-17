import {createApp} from 'vue';
import MixedImportPreview from './MixedImportPreview.vue';
import '../../style.css';
// Independent synthetic review entry. Course context never rewrites candidate targets.
createApp(MixedImportPreview,{courseContext:new URLSearchParams(location.search).get('course')||undefined}).mount('#app');
