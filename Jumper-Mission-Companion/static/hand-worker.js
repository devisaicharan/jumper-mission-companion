// Local recognition lives off the interface thread so Stop stays responsive.
let model=null;
self.onmessage=async({data})=>{
 try{
  if(data.type==='init'){
   // A classic worker lets MediaPipe load its unmodified WASM script with
   // importScripts. ES module workers cannot expose that script's factory.
   const {FilesetResolver,HandLandmarker}=await import('/vendor/vision/vision_bundle.mjs');
   const files=await FilesetResolver.forVisionTasks('/vendor/vision/wasm');
   model=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/vendor/hand_landmarker.task'},runningMode:'VIDEO',numHands:1,minHandDetectionConfidence:.7,minHandPresenceConfidence:.7,minTrackingConfidence:.7});
   self.postMessage({type:'ready'});
  }else if(data.type==='frame'){
   try{const result=model.detectForVideo(data.bitmap,data.timestamp);self.postMessage({type:'points',id:data.id,points:result.landmarks[0]?.map(p=>({x:1-p.x,y:p.y,z:p.z}))||[]});}
   finally{data.bitmap.close();}
  }
 }catch(e){self.postMessage({type:'error',id:data.id,message:e.message});}
};
