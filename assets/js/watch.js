/* Movie_editing — 播放頁 */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));
const fmt = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
const slug = new URLSearchParams(location.search).get('v');

fetch('assets/data/edits.json', { cache: 'no-cache' })
  .then(r => r.json())
  .then(d => {
    const edits = d.edits || [];
    const e = edits.find(x => x.slug === slug) || edits.find(x => x.featured) || edits[0];
    if (!e) { document.getElementById('title').textContent = '搵唔到呢條片'; return; }
    document.title = `${e.title} · Movie_editing`;

    const v = document.getElementById('player');
    v.src = e.video;
    v.poster = e.poster;

    document.getElementById('specs').textContent =
      [e.duration, e.size, '1080p · MP4'].filter(Boolean).join(' · ');

    document.getElementById('downloadSlot').innerHTML =
      `<a class="btn" href="${esc(e.video)}" download style="padding:9px 16px;font-size:13px">↓ 下載 MP4</a>`
      + (e.origin ? ` <a class="btn ghost" href="${esc(e.origin)}" target="_blank" rel="noopener" style="padding:9px 16px;font-size:13px">原版頁</a>` : '');

    document.getElementById('title').textContent = e.title;
    document.getElementById('desc').textContent = e.desc || '';
    document.getElementById('tags').innerHTML =
      (e.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('');
    document.getElementById('meta').innerHTML = [
      `<span>⏱ ${esc(e.duration)}</span>`,
      e.subtitle ? `<span>${esc(e.subtitle)}</span>` : '',
      e.date ? `<span>${esc(e.date)}</span>` : ''
    ].filter(Boolean).join('');

    document.getElementById('sourcenote').innerHTML = [
      e.source ? `原片：<b>${esc(e.source.name)}</b>${e.source.url ? ` — <a href="${esc(e.source.url)}" target="_blank" rel="noopener" style="color:var(--accent-2)">出處</a>` : ''}` : '',
      e.summary ? `<br>${esc(e.summary)}` : ''
    ].filter(Boolean).join('');

    const list = document.getElementById('chapters');
    const chapters = e.chapters || [];
    if (!chapters.length) {
      list.parentElement.style.display = 'none';
    }
    list.innerHTML = chapters.map(c =>
      `<li data-t="${c.t}">${c.img ? `<img class="cthumb" src="${esc(c.img)}" alt="" loading="lazy">` : ''}<span class="ts">${fmt(c.t)}</span><span>${esc(c.label)}</span></li>`).join('');

    [...list.children].forEach(li => {
      li.addEventListener('click', () => {
        v.currentTime = parseFloat(li.dataset.t) + 0.05;
        v.play();
      });
    });

    v.addEventListener('timeupdate', () => {
      const t = v.currentTime;
      let active = 0;
      chapters.forEach((c, i) => { if (t >= c.t) active = i; });
      [...list.children].forEach((li, i) => li.classList.toggle('active', i === active));
    });
  })
  .catch(() => { document.getElementById('title').textContent = '載入失敗'; });
