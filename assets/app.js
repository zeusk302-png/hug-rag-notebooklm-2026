document.querySelectorAll('.copy').forEach(button => {
  button.addEventListener('click', async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    const status = button.closest('.prompt').querySelector('.copy-state');
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const field = document.createElement('textarea');
        field.value = text; field.style.position = 'fixed'; field.style.left = '-9999px';
        document.body.appendChild(field); field.select();
        const ok = document.execCommand('copy'); field.remove();
        if (!ok) throw new Error('copy unavailable');
      }
      status.textContent = '복사됨 · 질문 상자에 붙여 넣으세요.';
      button.textContent = '복사됨';
    } catch {
      status.textContent = '자동 복사가 되지 않았습니다. 아래 문장을 직접 선택해 복사하세요.';
    }
  });
});
document.querySelector('.print')?.addEventListener('click', () => window.print());

const viewer = document.querySelector('.viewer');
if (viewer && typeof viewer.showModal === 'function') {
  const captures = [...document.querySelectorAll('figure')].map(figure => ({
    figure, image: figure.querySelector('img'),
    links: [...figure.querySelectorAll('[data-viewer]')]
  })).filter(capture => capture.image && capture.links.length);
  const image = viewer.querySelector('img');
  const title = viewer.querySelector('.viewer-title');
  const caption = viewer.querySelector('.viewer-caption');
  const frame = viewer.querySelector('.viewer-frame');
  const previous = viewer.querySelector('[data-previous]');
  const next = viewer.querySelector('[data-next]');
  const zoom = viewer.querySelector('[data-zoom]');
  let index = 0;
  let opener;
  function show(current) {
    index = current;
    const capture = captures[index];
    image.src = capture.image.src;
    image.alt = capture.image.alt;
    title.textContent = `실제 실행 화면 ${index + 1} / ${captures.length}`;
    caption.textContent = capture.image.alt;
    frame.classList.remove('is-fullsize');
    zoom.textContent = '원본 크기'; zoom.setAttribute('aria-pressed', 'false');
    previous.disabled = index === 0;
    next.disabled = index === captures.length - 1;
  }
  captures.forEach((capture, current) => capture.links.forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault(); opener = link; show(current); viewer.showModal();
    });
  }));
  previous.addEventListener('click', () => { if (index > 0) show(index - 1); });
  next.addEventListener('click', () => { if (index < captures.length - 1) show(index + 1); });
  zoom.addEventListener('click', () => {
    const full = frame.classList.toggle('is-fullsize');
    zoom.textContent = full ? '화면에 맞추기' : '원본 크기';
    zoom.setAttribute('aria-pressed', String(full));
  });
  viewer.querySelector('[data-close]').addEventListener('click', () => viewer.close());
  viewer.addEventListener('close', () => opener?.focus());
  viewer.addEventListener('click', event => {
    if (event.target !== viewer) return;
    const rect = viewer.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) viewer.close();
  });
}

const downloadDialog = document.querySelector('#download-dialog');
if (downloadDialog) {
 let downloadOpener;
 document.querySelectorAll('[data-download-open]').forEach(button => button.addEventListener('click',()=>{downloadOpener=button;downloadDialog.showModal();downloadDialog.scrollTop=0;}));
 downloadDialog.querySelector('[data-download-close]').addEventListener('click',()=>downloadDialog.close());
 downloadDialog.addEventListener('close',()=>downloadOpener?.focus());
 downloadDialog.addEventListener('click',event=>{if(event.target!==downloadDialog)return;const r=downloadDialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)downloadDialog.close();});
 downloadDialog.querySelector('.download-print').addEventListener('click',()=>{downloadDialog.close();window.print();});
}
