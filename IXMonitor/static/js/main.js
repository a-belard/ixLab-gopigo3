const btns = {
  forward: document.getElementById("forward"),
  backward: document.getElementById("backward"),
  left: document.getElementById("left"),
  right: document.getElementById("right"),
  stop: document.getElementById("stop")
};
let holdInterval = null;
function sendCommand(direction){
  fetch("/move",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({direction})});
}
function startHold(direction){
  sendCommand(direction);
  holdInterval = setInterval(()=>sendCommand(direction),200);
}
function stopHold(){
  clearInterval(holdInterval);
  holdInterval=null;
  sendCommand("stop");
}
for(const [dir,btn] of Object.entries(btns)){
  if(dir!=="stop"){
    btn.addEventListener("mousedown",()=>startHold(dir));
    btn.addEventListener("mouseup",stopHold);
    btn.addEventListener("mouseleave",stopHold);
  }
}
btns.stop.addEventListener("click",()=>sendCommand("stop"));
document.addEventListener("keydown",(e)=>{if(holdInterval)return;switch(e.key){case"ArrowUp":startHold("forward");break;case"ArrowDown":startHold("backward");break;case"ArrowLeft":startHold("left");break;case"ArrowRight":startHold("right");break;case" ":sendCommand("stop");break;}});
document.addEventListener("keyup",stopHold);
document.getElementById("goDoor").addEventListener("click",()=>fetch("/go_to_door",{method:"POST"}).then(resp=>resp.json()));
document.getElementById("returnStart").addEventListener("click",()=>fetch("/return_to_start",{method:"POST"}).then(resp=>resp.json()));
document.getElementById("takePic").addEventListener("click",()=>fetch("/take_picture",{method:"POST"}).then(resp=>resp.json()));
