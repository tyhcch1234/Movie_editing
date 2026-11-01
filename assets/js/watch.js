/* Movie_editing — player page */
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
    v.addEventListener('loadedmetadata', () => { if (e.runtime) v.playbackRate = 1; });

    document.getElementById('title').textContent = e.title;
    document.getElementById('desc').textContent = e.desc || '';
    document.getElementById('tags').innerHTML =
      (e.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
    document.getElementById('meta').innerHTML = [
      `<span>⏱ ${e.duration}</span>`,
      e.subtitle ? `<span>${e.subtitle}</span>` : '',
      e.date ? `<span>${e.date}</span>` : ''
    ].filter(Boolean).join('');

    document.getElementById('sourcenote').innerHTML = [
      e.source ? `原片：<b>${e.source.name}</b>${e.source.url ? ` — <a href="${e.source.url}" target="_blank" rel="noopener" style="color:var(--accent-2)">出處</a>` : ''}` : '',
      e.summary ? `<br>${e.summary}` : ''
    ].filter(Boolean).join('');

    const list = document.getElementById('chapters');
    const chapters = e.chapters || [];
    list.innerHTML = chapters.map((c, i) =>
      `<li data-t="${c.t}">${c.img ? `<img class="cthumb" src="${c.img}" alt="" loading="lazy">` : ''}<span class="ts">${fmt(c.t)}</span><span>${c.label}</span></li>`).join('');

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
