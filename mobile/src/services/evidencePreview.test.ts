import {describe,it,expect} from 'vitest';
import {boundingBox} from './evidencePreview';
describe('normalized evidence overlay',()=>{
 it('uses dimension ratios for PDF rectangles and OCR polygons',()=>{
  const expected={left:'10%',top:'20%',width:'30%',height:'20%'};
  expect(boundingBox({bbox:[10,20,40,40],page_width:100,page_height:100})).toEqual(expected);
  expect(boundingBox({bbox:[[20,40],[80,40],[80,80],[20,80]],page_width:200,page_height:200})).toEqual(expected);
 });
 it('does not invent an overlay for missing or invalid coordinates',()=>{
  for(const value of [{},{bbox:[1,2,3,4],page_width:0,page_height:100},{bbox:[10,20,10,40],page_width:100,page_height:100},{bbox:[[NaN,20]],page_width:100,page_height:100}])expect(boundingBox(value)).toBeNull();
 });
});
