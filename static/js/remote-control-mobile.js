(function(){
  'use strict';

  var stage=document.getElementById('remote-stage');
  var cursor=document.getElementById('mouse-cursor');
  var keyboardButton=document.getElementById('mobile-keyboard-button');
  var exitButton=document.getElementById('mobile-exit-button');
  var keyboardInput=document.getElementById('mobile-keyboard-input');
  var focusButton=document.getElementById('focus-btn');

  if(!stage||!cursor||!keyboardButton||!exitButton||!keyboardInput)return;

  var isMobile=window.matchMedia('(pointer: coarse)').matches||window.innerWidth<=820;
  var touchState=null;
  var singleTapTimer=null;
  var longPressTimer=null;
  var lastTapAt=0;
  var lastTwoFingerY=null;
  var autoFocusedForSession=false;

  function remoteIsActive(){
    return document.body.classList.contains('remote-control-active');
  }

  function safeFocus(element){
    try{
      element.focus({preventScroll:true});
    }catch(_error){
      element.focus();
    }
  }

  function pointInsideStage(clientX,clientY){
    var rect=stage.getBoundingClientRect();
    return clientX>=rect.left&&clientX<=rect.right&&clientY>=rect.top&&clientY<=rect.bottom;
  }

  function showCursor(clientX,clientY){
    var rect=stage.getBoundingClientRect();
    var x=Math.max(0,Math.min(rect.width,clientX-rect.left));
    var y=Math.max(0,Math.min(rect.height,clientY-rect.top));
    cursor.style.left=x+'px';
    cursor.style.top=y+'px';
    cursor.style.transform='translate3d(0,0,0)';
    cursor.classList.add('visible');
    cursor.hidden=false;
  }

  function hideCursor(){
    cursor.classList.remove('visible');
  }

  function mouseEvent(type,clientX,clientY,button){
    if(!remoteIsActive()||!pointInsideStage(clientX,clientY))return;
    showCursor(clientX,clientY);
    stage.dispatchEvent(new MouseEvent(type,{
      bubbles:true,
      cancelable:true,
      clientX:clientX,
      clientY:clientY,
      button:button||0,
      buttons:type==='mousemove'?1:0,
      view:window
    }));
  }

  function wheelEvent(deltaY){
    if(!remoteIsActive())return;
    try{
      stage.dispatchEvent(new WheelEvent('wheel',{
        bubbles:true,
        cancelable:true,
        deltaY:deltaY
      }));
    }catch(_error){
      var event=document.createEvent('Event');
      event.initEvent('wheel',true,true);
      event.deltaY=deltaY;
      stage.dispatchEvent(event);
    }
  }

  function keyEvent(key,options){
    if(!remoteIsActive())return;
    options=options||{};
    safeFocus(stage);
    stage.dispatchEvent(new KeyboardEvent('keydown',{
      key:key,
      bubbles:true,
      cancelable:true,
      ctrlKey:!!options.ctrlKey,
      altKey:!!options.altKey,
      shiftKey:!!options.shiftKey,
      metaKey:!!options.metaKey
    }));
  }

  function clearTimers(){
    if(longPressTimer){window.clearTimeout(longPressTimer);longPressTimer=null;}
  }

  function enterMobileFocus(){
    if(!isMobile||!remoteIsActive())return;
    if(!document.body.classList.contains('focus-mode')&&focusButton){
      focusButton.click();
    }
  }

  function syncMobileState(){
    if(!remoteIsActive()){
      autoFocusedForSession=false;
      hideCursor();
      keyboardInput.blur();
      return;
    }

    if(!autoFocusedForSession){
      autoFocusedForSession=true;
      window.setTimeout(enterMobileFocus,80);
    }
  }

  stage.addEventListener('pointermove',function(event){
    if(!remoteIsActive())return;
    if(event.pointerType==='mouse')showCursor(event.clientX,event.clientY);
  });

  stage.addEventListener('touchstart',function(event){
    if(!remoteIsActive())return;
    event.preventDefault();
    clearTimers();

    if(event.touches.length===2){
      touchState=null;
      lastTwoFingerY=(event.touches[0].clientY+event.touches[1].clientY)/2;
      return;
    }

    if(event.touches.length!==1)return;

    var touch=event.touches[0];
    touchState={
      startX:touch.clientX,
      startY:touch.clientY,
      lastX:touch.clientX,
      lastY:touch.clientY,
      moved:false,
      longPressed:false
    };

    mouseEvent('mousemove',touch.clientX,touch.clientY,0);

    longPressTimer=window.setTimeout(function(){
      if(!touchState||touchState.moved)return;
      touchState.longPressed=true;
      mouseEvent('contextmenu',touchState.lastX,touchState.lastY,2);
      if(navigator.vibrate)navigator.vibrate(35);
    },560);
  },{passive:false});

  stage.addEventListener('touchmove',function(event){
    if(!remoteIsActive())return;
    event.preventDefault();

    if(event.touches.length===2){
      clearTimers();
      touchState=null;
      var currentY=(event.touches[0].clientY+event.touches[1].clientY)/2;
      if(lastTwoFingerY!==null){
        var difference=currentY-lastTwoFingerY;
        if(Math.abs(difference)>=7){
          wheelEvent(difference>0?120:-120);
          lastTwoFingerY=currentY;
        }
      }else{
        lastTwoFingerY=currentY;
      }
      return;
    }

    if(!touchState||event.touches.length!==1)return;

    var touch=event.touches[0];
    touchState.lastX=touch.clientX;
    touchState.lastY=touch.clientY;

    if(Math.abs(touch.clientX-touchState.startX)>5||Math.abs(touch.clientY-touchState.startY)>5){
      touchState.moved=true;
      clearTimers();
    }

    mouseEvent('mousemove',touch.clientX,touch.clientY,0);
  },{passive:false});

  stage.addEventListener('touchend',function(event){
    if(!remoteIsActive())return;
    event.preventDefault();
    clearTimers();
    lastTwoFingerY=null;

    if(!touchState)return;

    var state=touchState;
    touchState=null;

    if(state.longPressed||state.moved)return;

    var now=Date.now();
    if(now-lastTapAt<310){
      lastTapAt=0;
      if(singleTapTimer){window.clearTimeout(singleTapTimer);singleTapTimer=null;}
      mouseEvent('dblclick',state.lastX,state.lastY,0);
      return;
    }

    lastTapAt=now;
    singleTapTimer=window.setTimeout(function(){
      mouseEvent('mousedown',state.lastX,state.lastY,0);
      singleTapTimer=null;
    },230);
  },{passive:false});

  stage.addEventListener('touchcancel',function(){
    clearTimers();
    touchState=null;
    lastTwoFingerY=null;
  },{passive:false});

  keyboardButton.addEventListener('click',function(event){
    event.preventDefault();
    if(!remoteIsActive())return;
    keyboardInput.value='';
    safeFocus(keyboardInput);
    window.setTimeout(function(){safeFocus(keyboardInput);},60);
  });

  keyboardInput.addEventListener('beforeinput',function(event){
    if(!remoteIsActive())return;
    if(event.inputType==='deleteContentBackward'){
      event.preventDefault();
      keyEvent('Backspace');
      keyboardInput.value='';
    }
  });

  keyboardInput.addEventListener('input',function(){
    if(!remoteIsActive()){
      keyboardInput.value='';
      return;
    }
    var value=keyboardInput.value;
    keyboardInput.value='';
    for(var index=0;index<value.length;index++){
      keyEvent(value.charAt(index));
    }
  });

  keyboardInput.addEventListener('keydown',function(event){
    if(!remoteIsActive())return;
    var supported={
      Enter:true,
      Tab:true,
      Escape:true,
      ArrowLeft:true,
      ArrowRight:true,
      ArrowUp:true,
      ArrowDown:true,
      Delete:true
    };
    if(!supported[event.key])return;
    event.preventDefault();
    keyEvent(event.key,{
      ctrlKey:event.ctrlKey,
      altKey:event.altKey,
      shiftKey:event.shiftKey,
      metaKey:event.metaKey
    });
  });

  exitButton.addEventListener('click',function(event){
    event.preventDefault();
    keyboardInput.blur();
    if(document.body.classList.contains('focus-mode')&&focusButton){
      focusButton.click();
    }
  });

  var observer=new MutationObserver(syncMobileState);
  observer.observe(document.body,{attributes:true,attributeFilter:['class']});

  window.addEventListener('orientationchange',function(){
    keyboardInput.blur();
  });

  document.addEventListener('visibilitychange',function(){
    if(document.hidden)keyboardInput.blur();
  });

  syncMobileState();
})();
