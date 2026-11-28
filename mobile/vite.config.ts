import { defineConfig } from 'vite'; import vue from '@vitejs/plugin-vue';
export default defineConfig({plugins:[vue()],build:{rollupOptions:{output:{
  assetFileNames:asset=>asset.name==='chi_sim.traineddata.gz'
    ? 'assets/ocr/chi_sim.traineddata.gz' : 'assets/[name]-[hash][extname]',
}}}});
