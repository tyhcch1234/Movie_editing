/* Movie_editing — home page (data-driven from assets/data/edits.json) */
const fmt = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

fetch('assets/data/edits.json', { cache: 'no-cache' })
  .then(r => r.json())
  .then(data => render(data))
  .catch(() => {
    document.getElementById('cards').innerHTML =
      '<div class="placeholder"><div><b>未能載入作品資料</b>請確認 assets/data/edits.json 存在。</div></div>';
  });

function render(data) {
  const edits = (data.edits || []).slice().sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  document.getElementById('lede').textContent = data.lede || '';

  const totalMin = edits.reduce((n, e) => n + (e.runtime || 0), 0) / 60;
  document.getElementById('stats').innerHTML = [
    [edits.length + ' 條', '剪好嘅作品'],
    [totalMin ? totalMin.toFixed(1) + ' 分鐘' : '—', '總片長'],
    [data.updated ? data.updated.replace(/-/g, '.') : '—', '最後更新']
  ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join('');

  document.getElementById('updated').textContent = data.updated ? '最後更新 ' + data.updated : '';
  document.getElementById('libraryNote').textContent =
    edits.length > 1 ? `共 ${edits.length} 條，按時間倒序` : '之後剪好嘅片會陸續加入';

  // featured = flag or newest
  const feat = edits.find(e => e.featured) || edits[0];
  if (feat) {
    document.getElementById('feature').innerHTML = `
      <div class="feature-grid">
        <a class="feature-media" href="watch.html?v=${feat.slug}">
          <img src="${feat.poster}" alt="${feat.title}">
          <div class="play"><div class="play-btn">▶</div></div>
        </a>
        <div class="feature-body">
          <div class="tagrow">
            <span class="tag hot">最新</span>
            ${(feat.tags || []).map(t => `<span class="tag">${t}</span>`).join('')}
          </div>
          <h2>${feat.title}</h2>
          <p>${feat.desc || ''}</p>
          <div class="meta-row">
            <span>⏱ ${feat.duration}</span>
            <span>${feat.subtitle || ''}</span>
            ${feat.chapters ? `<span>${feat.chapters.length} 個章節</span>` : ''}
          </div>
          <a class="btn" href="watch.html?v=${feat.slug}">▶ 播放</a>
        </div>
      </div>`;
  }

  const cards = edits.map(e => `
    <a class="card" href="watch.html?v=${e.slug}">
      <div class="thumb">
        <img src="${e.poster}" alt="${e.title}" loading="lazy">
        <span class="dur">${e.duration}</span>
      </div>
      <div class="body">
        <h4>${e.title}</h4>
        <p class="desc">${e.subtitle || ''}</p>
        <div class="foot"><span>${e.date || ''}</span><span>${(e.tags || [])[0] || ''}</span></div>
      </div>
    </a>`).join('');

  const placeholder = `
    <div class="placeholder">
      <div>
        <b>下一條片，等緊你</b>
        剪好之後放入 <code>videos/</code>，再喺 edits.json 加一項就會出現。
      </div>
    </div>`;

  document.getElementById('cards').innerHTML = cards + placeholder;
}
