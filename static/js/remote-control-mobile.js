(function(){
  'use strict';

  var stage=document.getElementById('remote-stage');
  var image=document.getElementById('live-img');
  var cursor=document.getElementById('mouse-cursor');
  var keyboardButton=document.getElementById('mobile-keyboard-button');
  var exitButton=document.getElementById('mobile-exit-button');
  var keyboardInput=document.getElementById('mobile-keyboard-input');
  var focusButton=document.getElementById('focus-btn');

  if(!stage||!image||!cursor||!keyboardButton||!exitButton||!keyboardInput)return;

  var isMobile=window.matchMedia('(pointer: coarse)').matches||window.innerWidth<=820;
  var TRACKPAD_SPEED=0.92;
  var TRACKPAD_DEAD_ZONE=0.65;
  var TRACKPAD_MAX_STEP=18;
  var TRACKPAD_SMOOTHING=0.55;

  var touchState=null;
  var virtualCursor=null;
  var smoothedDelta={x:0,y:0};
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

  function clamp(value,min,max){
    return Math.max(min,Math.min(max,value));
  }

  function imageMetrics(){
    var rect=stage.getBoundingClientRect();
    var width=rect.width;
    var height=rect.height;
    var offsetX=0;
    var offsetY=0;

    if(!image.classList.contains('hidden')&&image.naturalWidth&&image.naturalHeight){
      var imageRatio=image.naturalWidth/image.naturalHeight;
      var boxRatio=rect.width/rect.height;

      if(boxRatio>imageRatio){
        width=height*imageRatio;
        offsetX=(rect.width-width)/2;
      }else{
        height=width/imageRatio;
        offsetY=(rect.height-height)/2;
      }
    }

    return {
      rect:rect,
      width:Math.max(width,1),
      height:Math.max(height,1),
      offsetX:offsetX,
      offsetY:offsetY
    };
  }

  function ensureVirtualCursor(){
    if(!virtualCursor){
      virtualCursor={x:0.5,y:0.5};
    }
    return virtualCursor;
  }

  function virtualClientPoint(){
    var metrics=imageMetrics();
    var position=ensureVirtualCursor();

    return {
      clientX:metrics.rect.left+metrics.offsetX+(position.x*metrics.width),
      clientY:metrics.rect.top+metrics.offsetY+(position.y*metrics.height),
      localX:metrics.offsetX+(position.x*metrics.width),
      localY:metrics.offsetY+(position.y*metrics.height)
    };
  }

  function renderVirtualCursor(){
    var point=virtualClientPoint();
    cursor.style.left=point.localX+'px';
    cursor.style.top=point.localY+'px';
    cursor.style.transform='translate3d(0,0,0)';
    cursor.classList.add('visible');
    cursor.hidden=false;
  }

  function hideCursor(){
    cursor.classList.remove('visible');
  }

  function setVirtualCursorFromClient(clientX,clientY){
    var metrics=imageMetrics();
    var localX=clientX-metrics.rect.left-metrics.offsetX;
    var localY=clientY-metrics.rect.top-metrics.offsetY;

    if(localX<0||localY<0||localX>metrics.width||localY>metrics.height){
      return false;
    }

    virtualCursor={
      x:clamp(localX/metrics.width,0,1),
      y:clamp(localY/metrics.height,0,1)
    };
    renderVirtualCursor();
    return true;
  }

  function dispatchMouseAtVirtual(type,button){
    if(!remoteIsActive())return;
    var point=virtualClientPoint();
    renderVirtualCursor();

    stage.dispatchEvent(new MouseEvent(type,{
      bubbles:true,
      cancelable:true,
      clientX:point.clientX,
      clientY:point.clientY,
      button:button||0,
      buttons:0,
      view:window
    }));
  }

  function resetTrackpadFilter(){
    smoothedDelta.x=0;
    smoothedDelta.y=0;
  }

  function stabilizeDelta(rawX,rawY){
    rawX=clamp(rawX,-TRACKPAD_MAX_STEP,TRACKPAD_MAX_STEP);
    rawY=clamp(rawY,-TRACKPAD_MAX_STEP,TRACKPAD_MAX_STEP);

    if(Math.abs(rawX)<TRACKPAD_DEAD_ZONE)rawX=0;
    if(Math.abs(rawY)<TRACKPAD_DEAD_ZONE)rawY=0;

    var absX=Math.abs(rawX);
    var absY=Math.abs(rawY);

    if(absX>absY*2.2&&absY<3){
      rawY=0;
    }else if(absY>absX*2.2&&absX<3){
      rawX=0;
    }

    smoothedDelta.x=(smoothedDelta.x*(1-TRACKPAD_SMOOTHING))+(rawX*TRACKPAD_SMOOTHING);
    smoothedDelta.y=(smoothedDelta.y*(1-TRACKPAD_SMOOTHING))+(rawY*TRACKPAD_SMOOTHING);

    if(Math.abs(smoothedDelta.x)<0.35)smoothedDelta.x=0;
    if(Math.abs(smoothedDelta.y)<0.35)smoothedDelta.y=0;

    return {x:smoothedDelta.x,y:smoothedDelta.y};
  }

  function moveVirtualCursor(deltaX,deltaY){
    if(!remoteIsActive())return;

    var stable=stabilizeDelta(deltaX,deltaY);
    if(stable.x===0&&stable.y===0)return;

    var metrics=imageMetrics();
    var position=ensureVirtualCursor();
    position.x=clamp(position.x+(stable.x*TRACKPAD_SPEED/metrics.width),0,1);
    position.y=clamp(position.y+(stable.y*TRACKPAD_SPEED/metrics.height),0,1);

    dispatchMouseAtVirtual('mousemove',0);
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

  function keepKeyboardOpen(){
    if(!remoteIsActive()||document.hidden)return;
    window.setTimeout(function(){
      if(document.activeElement!==keyboardInput){
        safeFocus(keyboardInput);
      }
    },0);
  }

  function clearTimers(){
    if(longPressTimer){
      window.clearTimeout(longPressTimer);
      longPressTimer=null;
    }
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
      virtualCursor=null;
      resetTrackpadFilter();
      hideCursor();
      keyboardInput.blur();
      return;
    }

    ensureVirtualCursor();
    renderVirtualCursor();

    if(!autoFocusedForSession){
      autoFocusedForSession=true;
      window.setTimeout(enterMobileFocus,80);
    }
  }

  stage.addEventListener('pointermove',function(event){
    if(!remoteIsActive()||event.pointerType!=='mouse')return;
    setVirtualCursorFromClient(event.clientX,event.clientY);
  });

  stage.addEventListener('touchstart',function(event){
    if(!remoteIsActive())return;
    event.preventDefault();
    clearTimers();
    resetTrackpadFilter();

    ensureVirtualCursor();
    renderVirtualCursor();

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
      lastTouchX:touch.clientX,
      lastTouchY:touch.clientY,
      moved:false,
      longPressed:false
    };

    longPressTimer=window.setTimeout(function(){
      if(!touchState||touchState.moved)return;
      touchState.longPressed=true;
      dispatchMouseAtVirtual('contextmenu',2);
      if(navigator.vibrate)navigator.vibrate(35);
    },560);
  },{passive:false});

  stage.addEventListener('touchmove',function(event){
    if(!remoteIsActive())return;
    event.preventDefault();

    if(event.touches.length===2){
      clearTimers();
      touchState=null;
      resetTrackpadFilter();

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
    var deltaX=touch.clientX-touchState.lastTouchX;
    var deltaY=touch.clientY-touchState.lastTouchY;

    touchState.lastTouchX=touch.clientX;
    touchState.lastTouchY=touch.clientY;

    if(Math.abs(touch.clientX-touchState.startX)>5||Math.abs(touch.clientY-touchState.startY)>5){
      touchState.moved=true;
      clearTimers();
    }

    moveVirtualCursor(deltaX,deltaY);
  },{passive:false});

  stage.addEventListener('touchend',function(event){
    if(!remoteIsActive())return;
    event.preventDefault();
    clearTimers();
    resetTrackpadFilter();
    lastTwoFingerY=null;

    if(!touchState)return;

    var state=touchState;
    touchState=null;

    if(state.longPressed||state.moved)return;

    var now=Date.now();
    if(now-lastTapAt<310){
      lastTapAt=0;
      if(singleTapTimer){
        window.clearTimeout(singleTapTimer);
        singleTapTimer=null;
      }
      dispatchMouseAtVirtual('dblclick',0);
      return;
    }

    lastTapAt=now;
    singleTapTimer=window.setTimeout(function(){
      dispatchMouseAtVirtual('mousedown',0);
      singleTapTimer=null;
    },230);
  },{passive:false});

  stage.addEventListener('touchcancel',function(){
    clearTimers();
    resetTrackpadFilter();
    touchState=null;
    lastTwoFingerY=null;
  },{passive:false});

  keyboardButton.addEventListener('click',function(event){
    event.preventDefault();
    if(!remoteIsActive())return;
    keyboardInput.value='';
    safeFocus(keyboardInput);
    window.setTimeout(function(){safeFocus(keyboardInput);},80);
  });

  keyboardInput.addEventListener('beforeinput',function(event){
    if(!remoteIsActive())return;

    if(event.inputType==='deleteContentBackward'){
      event.preventDefault();
      keyEvent('Backspace');
      keyboardInput.value='';
      keepKeyboardOpen();
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

    keepKeyboardOpen();
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
    keepKeyboardOpen();
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

  image.addEventListener('load',function(){
    if(remoteIsActive()){
      ensureVirtualCursor();
      renderVirtualCursor();
    }
  });

  window.addEventListener('resize',function(){
    if(remoteIsActive()&&virtualCursor){
      renderVirtualCursor();
    }
  });

  window.addEventListener('orientationchange',function(){
    keyboardInput.blur();
    resetTrackpadFilter();
    window.setTimeout(function(){
      if(remoteIsActive()&&virtualCursor){
        renderVirtualCursor();
      }
    },250);
  });

  document.addEventListener('visibilitychange',function(){
    if(document.hidden){
      keyboardInput.blur();
      resetTrackpadFilter();
    }
  });

  syncMobileState();
})();