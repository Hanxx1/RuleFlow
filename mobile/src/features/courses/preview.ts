// Standalone development entry; the main app uses the lazy-loaded /courses route.
import {createApp} from 'vue';
import CoursePreview from './CoursePreview.vue';
import '../../style.css';
createApp(CoursePreview).mount('#app');
