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

// Educational exact-substring retrieval; no embedding or generative model.
const labForm = document.querySelector('#lab-form');
if (labForm) {
 const corpus = JSON.parse(document.querySelector('#lab-corpus').textContent);
 let savedRecord='';
 const addText=(tag,text,parent)=>{const node=document.createElement(tag);node.textContent=text;parent.append(node);return node;};
 labForm.addEventListener('submit', event=>{
  event.preventDefault();
  const query=document.querySelector('#lab-query').value.trim();
  const terms=[...new Set(query.split(/\s+/).filter(Boolean))];
  const k=Number(document.querySelector('#lab-k').value);
  const current=document.querySelector('#lab-current').checked;
  const hits=corpus.filter(c=>!current||c.current).map(c=>({...c,score:terms.filter(t=>c.text.includes(t)).length})).filter(c=>c.score>0).sort((a,b)=>b.score-a.score||a.id.localeCompare(b.id));
  const chosen=hits.slice(0,k);
  const out=document.querySelector('#lab-results');out.replaceChildren();
  document.querySelector('#lab-status').textContent=`후보 ${hits.length}개 · 전달 ${chosen.length}개 · 단어 포함 수로 순위 결정`;
  hits.forEach((c,i)=>{const card=document.createElement('article');card.className='lab-hit';addText('h3',`${c.id} · ${c.version} · 점수 ${c.score} · ${i<k?'전달':'후보만'}`,card);addText('p',c.text,card);out.append(card);});
  const context=`질문: ${query}\n지시: 제공된 근거와 조건을 대조하고, 부족하면 확인 필요로 표시.\n\n`+(chosen.length?chosen.map(c=>`[${c.id} / ${c.version}] ${c.text}`).join('\n'):'근거 없음 — 답을 확정하지 말고 자료와 검색 표현을 확인.');
  document.querySelector('#lab-context').textContent=context;
  savedRecord=`교육용 단순 키워드 검색 기록 (AI 생성 답변 아님)\n유효 자료만: ${current} / 전달 수: ${k}\n후보: ${hits.map(c=>c.id+':'+c.score).join(', ')}\n\n${context}`;
  document.querySelector('#lab-save').disabled=false;
 });
 document.querySelector('#lab-save').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob(['\ufeff'+savedRecord],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='rag-search-record.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
}
