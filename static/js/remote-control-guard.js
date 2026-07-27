(function(){
  'use strict';

  document.addEventListener('dblclick',function(event){
    var stage=event.target.closest&&event.target.closest('#remote-stage');
    if(!stage)return;
    event.preventDefault();
    event.stopImmediatePropagation();
  },true);

  var config=window.BESTHOME_REMOTE||{};
  if(config.online&&!config.remoteCapable){
    var startButton=document.getElementById('remote-start');
    var title=document.getElementById('remote-session-title');
    var message=document.getElementById('remote-session-message');
    var badge=document.getElementById('remote-session-badge');
    if(startButton)startButton.disabled=true;
    if(title)title.textContent='Yeni agent EXE tələb olunur';
    if(message)message.textContent='Bu kompüter online-dır, amma quraşdırılmış agent remote idarəetməni dəstəkləmir.';
    if(badge){
      badge.className='remote-session-badge error';
      badge.innerHTML='<i class="status-dot"></i>Hazır deyil';
    }
  }
})();
