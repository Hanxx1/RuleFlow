import {createWorker,OEM} from 'tesseract.js'
import workerPath from 'tesseract.js/dist/worker.min.js?url'
import corePath from 'tesseract.js-core/tesseract-core-lstm.wasm.js?url'
import modelPath from '@tesseract.js-data/chi_sim/4.0.0_best_int/chi_sim.traineddata.gz?url'

export async function readScan(canvas:HTMLCanvasElement){
  const langPath=new URL('.',new URL(modelPath,document.baseURI)).href
  const worker=await createWorker('chi_sim',OEM.LSTM_ONLY,{
    langPath,
    workerPath,corePath,cacheMethod:'none',workerBlobURL:false,
  })
  try{return (await worker.recognize(canvas)).data.text}
  finally{await worker.terminate()}
}
