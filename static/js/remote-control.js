(function(){
  'use strict';

  var config=window.BESTHOME_REMOTE||{};
  var agentName=config.agentName||'';
  var csrfToken=config.csrfToken||'';
  var isOnline=!!config.online;

  var startBtn=document.getElementById('remote-start');
  var stopBtn=document.getElementById('remote-stop');
  var focusBtn=document.getElementById('focus-btn');
  var stage=document.getElementById('remote-stage');
  var image=document.getElementById('live-img');
  var empty=document.getElementById('live-empty');
  var liveStatus=document.getElementById('live-status');
  var liveMeta=document.getElementById('live-meta');
  var activeBanner=document.getElementById('remote-active-banner');
  var focusHint=document.getElementById('remote-focus-hint');
  var sessionTitle=document.getElementById('remote-session-title');
  var sessionMessage=document.getElementById('remote-session-message');
  var sessionBadge=document.getElementById('remote-session-badge');
  var activityList=document.getElementById('activity-list');
  var activityToggle=document.getElementById('activity-toggle');

  var sessionId=null;
  var remoteActive=false;
  var statusTimer=null;
  var screenTimer=null;
  var commandTimer=null;
  var commandBuffer=[];
  var pendingMove=null;
  var sendingCommands=false;
  var showAllActivity=false;
  var activityRows=[];

  function escapeHtml(value){
    return String(value||'').replace(/[&<>\"]/g,function(character){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[character];
    });
  }

  function apiFetch(url,options){
    options=options||{};
    options.headers=options.headers||{};
    if(options.method&&options.method!=='GET'){
      options.headers['Content-Type']='application/json';
      options.headers['X-CSRF-Token']=csrfToken;
    }
    return fetch(url,options).then(function(response){
      return response.json().catch(function(){return {};}).then(function(data){
        if(!response.ok){
          throw new Error(data.error||('HTTP '+response.status));
        }
        return data;
      });
    });
  }

  function setLiveStatus(text,active){
    liveStatus.innerHTML='<i class="status-dot"></i>'+escapeHtml(text);
    liveStatus.classList.toggle('active',!!active);
  }

  function showEmpty(title,description){
    image.classList.add('hidden');
    empty.classList.remove('hidden');
    empty.querySelector('b').textContent=title;
    empty.querySelector('span').textContent=description;
  }

  function showImage(){
    empty.classList.add('hidden');
    image.classList.remove('hidden');
  }

  function refreshScreen(){
    fetch('/api/agent/'+encodeURIComponent(agentName)+'/last')
      .then(function(response){if(!response.ok)throw new Error('no-image');return response.json();})
      .then(function(data){
        if(!data.ok||!data.filename)throw new Error('no-image');
        image.onload=function(){showImage();};
        image.onerror=function(){showEmpty('Görüntü açıla bilmədi','Agent yeni görüntü göndərdikdə avtomatik bərpa olunacaq.');};
        image.src='/screens/'+encodeURIComponent(data.filename)+'?t='+Date.now();
        liveMeta.textContent='Son görüntü: '+data.created_at+(data.active_url?' · '+data.active_url:'');
        setLiveStatus('Görüntü aktivdir',true);
      })
      .catch(function(){
        setLiveStatus('Görüntü yoxdur',false);
        showEmpty('Görüntü yoxdur','Agent offline ola bilər və ya hələ ekran görüntüsü göndərməyib.');
      });
  }

  function setSessionView(state,title,message){
    sessionBadge.className='remote-session-badge '+state;
    var labels={idle:'Gözləyir',pending:'Təsdiq gözləyir',active:'Aktivdir',error:'Dayandırılıb'};
    sessionBadge.innerHTML='<i class="status-dot"></i>'+labels[state];
    sessionTitle.textContent=title;
    sessionMessage.textContent=message;
  }

  function enableRemoteControls(){
    if(remoteActive)return;
    remoteActive=true;
    document.body.classList.add('remote-control-active');
    stage.classList.add('remote-enabled');
    activeBanner.classList.remove('hidden');
    startBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');
    setSessionView('active','Uzaqdan idarəetmə aktivdir','Ekrana klik etdikdən sonra mouse və klaviatura komandaları qarşı kompüterə göndərilir.');
  }

  function disableRemoteControls(reason){
    remoteActive=false;
    document.body.classList.remove('remote-control-active');
    stage.classList.remove('remote-enabled');
    focusHint.classList.add('hidden');
    activeBanner.classList.add('hidden');
    stopBtn.classList.add('hidden');
    startBtn.classList.remove('hidden');
    startBtn.disabled=!isOnline;
    commandBuffer=[];
    pendingMove=null;
    if(reason){
      setSessionView('error','İdarəetmə dayandırıldı',reason);
    }else{
      setSessionView('idle','İdarəetmə aktiv deyil','Sessiya başladıldıqda qarşı kompüterdə icazə pəncərəsi görünəcək.');
    }
  }

  function startRemote(){
    if(!isOnline||sessionId)return;
    startBtn.disabled=true;
    setSessionView('pending','İcazə sorğusu göndərilir','Qarşı kompüterdə təsdiq pəncərəsi açılacaq.');
    apiFetch('/api/remote/'+encodeURIComponent(agentName)+'/start',{
      method:'POST',
      body:'{}'
    }).then(function(data){
      sessionId=data.session.id;
      setSessionView('pending','Kompüterdən təsdiq gözlənilir','İstifadəçi icazə verdikdə idarəetmə avtomatik aktivləşəcək.');
      pollSessionStatus();
      statusTimer=window.setInterval(pollSessionStatus,1000);
    }).catch(function(error){
      startBtn.disabled=!isOnline;
      setSessionView('error','Sessiya başlamadı',error.message);
    });
  }

  function pollSessionStatus(){
    if(!sessionId)return;
    apiFetch('/api/remote/'+encodeURIComponent(sessionId)+'/status',{method:'GET'})
      .then(function(data){
        var remoteSession=data.session;
        if(remoteSession.status==='pending'){
          var pendingMessage=remoteSession.agent_connected?
            'Agent sorğunu aldı. İstifadəçi cavabı gözlənilir.':
            'Agentin remote modulu ilə əlaqə gözlənilir.';
          setSessionView('pending','Kompüterdən təsdiq gözlənilir',pendingMessage);
          return;
        }
        if(remoteSession.status==='active'){
          enableRemoteControls();
          return;
        }
        if(remoteSession.status==='ended'){
          var reasons={
            admin_stopped:'Sessiya administrator tərəfindən dayandırıldı.',
            agent_denied:'İstifadəçi idarəetməyə icazə vermədi.',
            agent_stopped:'İstifadəçi qarşı kompüterdə idarəetməni dayandırdı.',
            agent_error:'Agent remote modulu xəta verdi.',
            admin_disconnected:'Panel bağlantısı kəsildiyi üçün sessiya bağlandı.',
            agent_disconnected:'Agent bağlantısı kəsildiyi üçün sessiya bağlandı.',
            consent_timeout:'İcazə vaxtında təsdiqlənmədi.',
            expired:'Sessiyanın vaxtı bitdi.'
          };
          endLocalSession(reasons[remoteSession.ended_reason]||'Remote sessiya bağlandı.');
        }
      })
      .catch(function(error){
        endLocalSession(error.message);
      });
  }

  function stopRemote(){
    if(!sessionId){disableRemoteControls();return;}
    stopBtn.disabled=true;
    apiFetch('/api/remote/'+encodeURIComponent(sessionId)+'/stop',{
      method:'POST',
      body:'{}'
    }).catch(function(){}).finally(function(){
      stopBtn.disabled=false;
      endLocalSession('Sessiya administrator tərəfindən dayandırıldı.');
    });
  }

  function endLocalSession(reason){
    if(statusTimer){window.clearInterval(statusTimer);statusTimer=null;}
    sessionId=null;
    disableRemoteControls(reason);
  }

  function actualImagePoint(event){
    if(image.classList.contains('hidden')||!image.naturalWidth||!image.naturalHeight)return null;
    var rect=stage.getBoundingClientRect();
    var imageRatio=image.naturalWidth/image.naturalHeight;
    var boxRatio=rect.width/rect.height;
    var width=rect.width;
    var height=rect.height;
    var offsetX=0;
    var offsetY=0;
    if(boxRatio>imageRatio){
      width=height*imageRatio;
      offsetX=(rect.width-width)/2;
    }else{
      height=width/imageRatio;
      offsetY=(rect.height-height)/2;
    }
    var localX=event.clientX-rect.left-offsetX;
    var localY=event.clientY-rect.top-offsetY;
    if(localX<0||localY<0||localX>width||localY>height)return null;
    return {x:localX/width,y:localY/height};
  }

  function queueCommand(type,payload){
    if(!remoteActive||!sessionId)return;
    if(type==='move'){
      pendingMove={type:type,payload:payload};
    }else{
      commandBuffer.push({type:type,payload:payload});
    }
    if(!commandTimer){
      commandTimer=window.setTimeout(flushCommands,45);
    }
  }

  function flushCommands(){
    commandTimer=null;
    if(!remoteActive||!sessionId||sendingCommands)return;
    var commands=[];
    if(pendingMove){commands.push(pendingMove);pendingMove=null;}
    while(commandBuffer.length&&commands.length<50){commands.push(commandBuffer.shift());}
    if(!commands.length)return;
    sendingCommands=true;
    apiFetch('/api/remote/'+encodeURIComponent(sessionId)+'/commands',{
      method:'POST',
      body:JSON.stringify({commands:commands})
    }).catch(function(error){
      setSessionView('error','Komanda göndərilmədi',error.message);
    }).finally(function(){
      sendingCommands=false;
      if(pendingMove||commandBuffer.length){commandTimer=window.setTimeout(flushCommands,30);}
    });
  }

  function normalizeKey(key){
    var aliases={
      Control:'CTRL',Escape:'ESCAPE',' ':'SPACE',ArrowLeft:'ARROWLEFT',
      ArrowRight:'ARROWRIGHT',ArrowUp:'ARROWUP',ArrowDown:'ARROWDOWN',
      PageUp:'PAGEUP',PageDown:'PAGEDOWN',CapsLock:'CAPSLOCK',
      NumLock:'NUMLOCK',ScrollLock:'SCROLLLOCK',PrintScreen:'PRINTSCREEN',
      ContextMenu:'CONTEXTMENU',Meta:'META',OS:'META'
    };
    return aliases[key]||String(key||'').toUpperCase();
  }

  stage.addEventListener('mousemove',function(event){
    if(!remoteActive)return;
    var point=actualImagePoint(event);
    if(point)queueCommand('move',point);
  });

  stage.addEventListener('mousedown',function(event){
    if(!remoteActive)return;
    var point=actualImagePoint(event);
    if(!point)return;
    event.preventDefault();
    stage.focus();
    queueCommand('move',point);
    if(event.button===0)queueCommand('click',{button:'left',count:1});
    if(event.button===1)queueCommand('click',{button:'middle',count:1});
  });

  stage.addEventListener('dblclick',function(event){
    if(!remoteActive)return;
    var point=actualImagePoint(event);
    if(!point)return;
    event.preventDefault();
    queueCommand('move',point);
    queueCommand('click',{button:'left',count:2});
  });

  stage.addEventListener('contextmenu',function(event){
    if(!remoteActive)return;
    var point=actualImagePoint(event);
    if(!point)return;
    event.preventDefault();
    stage.focus();
    queueCommand('move',point);
    queueCommand('click',{button:'right',count:1});
  });

  stage.addEventListener('wheel',function(event){
    if(!remoteActive)return;
    event.preventDefault();
    var delta=event.deltaY>0?-120:120;
    queueCommand('wheel',{delta:delta});
  },{passive:false});

  stage.addEventListener('focus',function(){
    if(remoteActive)focusHint.classList.remove('hidden');
  });

  stage.addEventListener('blur',function(){focusHint.classList.add('hidden');});

  stage.addEventListener('keydown',function(event){
    if(!remoteActive)return;
    if(event.key==='Escape'){
      stage.blur();
      if(document.body.classList.contains('focus-mode'))setFocus(false);
      event.preventDefault();
      return;
    }
    if(['Control','Shift','Alt','Meta'].indexOf(event.key)!==-1){
      event.preventDefault();
      return;
    }

    var key=normalizeKey(event.key);
    if(event.ctrlKey||event.altKey||event.metaKey){
      var keys=[];
      if(event.ctrlKey)keys.push('CTRL');
      if(event.altKey)keys.push('ALT');
      if(event.shiftKey)keys.push('SHIFT');
      if(event.metaKey)keys.push('META');
      keys.push(key);
      if(keys.join('+')==='CTRL+ALT+DELETE'){
        setSessionView('active','Uzaqdan idarəetmə aktivdir','Ctrl+Alt+Delete Windows tərəfindən bloklanır və göndərilmədi.');
      }else{
        queueCommand('hotkey',{keys:keys});
      }
      event.preventDefault();
      return;
    }

    if(event.key.length===1){
      queueCommand('text',{text:event.key});
    }else{
      queueCommand('key',{key:key});
    }
    event.preventDefault();
  });

  stage.addEventListener('paste',function(event){
    if(!remoteActive)return;
    var text=(event.clipboardData||window.clipboardData).getData('text');
    if(!text)return;
    event.preventDefault();
    for(var index=0;index<text.length;index+=128){
      queueCommand('text',{text:text.slice(index,index+128)});
    }
  });

  function renderActivity(){
    if(!activityRows.length){
      activityList.innerHTML='<div class="activity-empty">Bu gün üçün aktivlik qeydə alınmayıb.</div>';
      activityToggle.hidden=true;
      return;
    }
    var rows=showAllActivity?activityRows:activityRows.slice(0,5);
    activityList.innerHTML=rows.map(function(item){
      return '<div class="activity-item"><div><b>'+escapeHtml(item.process||'—')+'</b><span>'+escapeHtml(item.url||item.window||'—')+'</span></div><div class="activity-time"><b>'+escapeHtml(item.formatted_duration)+'</b><span>'+escapeHtml(item.first_seen)+' - '+escapeHtml(item.last_seen)+'</span></div></div>';
    }).join('');
    activityToggle.hidden=activityRows.length<=5;
    activityToggle.textContent=showAllActivity?'Az göstər':'Hamısını göstər';
  }

  function fetchActivity(){
    fetch('/api/agent/'+encodeURIComponent(agentName)+'/activity/today')
      .then(function(response){return response.json();})
      .then(function(data){activityRows=data.activities||[];renderActivity();})
      .catch(function(){activityList.innerHTML='<div class="activity-empty">Aktivlik məlumatları yüklənmədi.</div>';});
  }

  function setFocus(enabled){
    document.body.classList.toggle('focus-mode',enabled);
    focusBtn.innerHTML=enabled?'Normal görünüş':'<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>Tam ekran';
    if(enabled&&remoteActive)stage.focus();
  }

  startBtn.addEventListener('click',startRemote);
  stopBtn.addEventListener('click',stopRemote);
  activityToggle.addEventListener('click',function(){showAllActivity=!showAllActivity;renderActivity();});
  focusBtn.addEventListener('click',function(){
    var enabled=!document.body.classList.contains('focus-mode');
    setFocus(enabled);
    if(enabled&&document.fullscreenEnabled){document.documentElement.requestFullscreen().catch(function(){});}
    else if(!enabled&&document.fullscreenElement){document.exitFullscreen();}
  });
  document.addEventListener('fullscreenchange',function(){if(!document.fullscreenElement)setFocus(false);});

  var modal=document.getElementById('modal');
  var modalImg=document.getElementById('modal-img');
  image.addEventListener('click',function(){
    if(remoteActive||document.body.classList.contains('focus-mode')||image.classList.contains('hidden'))return;
    modalImg.src=image.src;
    modal.style.display='flex';
  });
  document.getElementById('modal-close').addEventListener('click',function(){modal.style.display='none';});
  modal.addEventListener('click',function(event){if(event.target===modal)modal.style.display='none';});

  window.addEventListener('beforeunload',function(){
    if(!sessionId)return;
    fetch('/api/remote/'+encodeURIComponent(sessionId)+'/stop',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},
      body:'{}',
      keepalive:true
    }).catch(function(){});
  });

  if(!isOnline){
    startBtn.disabled=true;
    setSessionView('error','Agent offline-dır','Uzaqdan idarəetmə üçün agent online olmalıdır.');
  }
  refreshScreen();
  screenTimer=window.setInterval(refreshScreen,500);
  fetchActivity();
  window.setInterval(fetchActivity,30000);
})();
