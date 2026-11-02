/* Movie_editing — 首頁：統計 + 精選 + 作品庫（資料來自 assets/data/edits.json） */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

fetch('assets/data/edits.json', { cache: 'no-cache' })
  .then(r => r.json())
  .then(render)
  .catch(() => {
    document.getElementById('cards').innerHTML =
      '<div class="placeholder"><div><b>未能載入作品資料</b>請確認 assets/data/edits.json 存在。</div></div>';
  });

function render(data) {
  const edits = (data.edits || []).slice()
    .sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  if (data.lede) document.getElementById('lede').textContent = data.lede;

  /* ---- stats ---- */
  const totalMin = edits.reduce((n, e) => n + (e.runtime || 0), 0) / 60;
  document.getElementById('stats').innerHTML = [
    [edits.length + ' 條', '已完成作品'],
    [totalMin ? totalMin.toFixed(0) + ' 分鐘' : '—', '總片長'],
    [data.updated ? data.updated.replace(/-/g, '.') : '—', '最後更新']
  ].map(([b, s]) => `<div class="stat"><b>${esc(b)}</b><span>${esc(s)}</span></div>`).join('');

  document.getElementById('updated').textContent =
    data.updated ? '最後更新 ' + data.updated : '';
  document.getElementById('libraryNote').textContent = edits.length
    ? `共 ${edits.length} 條 · 可以播放，亦可以直接下載`
    : '第一條片剪好就會出現喺度';

  /* ---- featured ---- */
  const feat = edits.find(e => e.featured) || edits[0];
  const featBox = document.getElementById('feature');
  if (feat) {
    featBox.innerHTML = `
      <div class="feature-grid">
        <a class="feature-media" href="watch.html?v=${encodeURIComponent(feat.slug)}">
          <img src="${esc(feat.poster)}" alt="${esc(feat.title)}">
          <div class="play"><div class="play-btn">▶</div></div>
        </a>
        <div class="feature-body">
          <div class="tagrow">
            <span class="tag hot">最新</span>
            ${(feat.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('')}
          </div>
          <h3>${esc(feat.title)}</h3>
          <p>${esc(feat.desc || '')}</p>
          <div class="meta-row">
            <span>⏱ ${esc(feat.duration)}</span>
            ${feat.subtitle ? `<span>${esc(feat.subtitle)}</span>` : ''}
            ${feat.size ? `<span>${esc(feat.size)}</span>` : ''}
          </div>
          <div class="feature-actions">
            <a class="btn" href="watch.html?v=${encodeURIComponent(feat.slug)}">▶ 播放</a>
            <a class="btn ghost" href="${esc(feat.video)}" download>↓ 下載 MP4</a>
          </div>
        </div>
      </div>`;
  } else {
    featBox.remove();
  }

  /* ---- cards（連精選一齊列，作為完整清單） ---- */
  const cards = edits.map(e => `
    <div class="card">
      <a class="thumb" href="watch.html?v=${encodeURIComponent(e.slug)}">
        <img src="${esc(e.poster)}" alt="${esc(e.title)}" loading="lazy">
        <span class="dur">${esc(e.duration)}</span>
      </a>
      <div class="body">
        <h4><a href="watch.html?v=${encodeURIComponent(e.slug)}">${esc(e.title)}</a></h4>
        <p class="desc">${esc(e.subtitle || '')}</p>
        <div class="foot">
          <span>${esc(e.date || '')}${e.size ? ' · ' + esc(e.size) : ''}</span>
          <span class="acts">
            <a href="watch.html?v=${encodeURIComponent(e.slug)}">▶ 播放</a>
            <a href="${esc(e.video)}" download>↓ 下載</a>
          </span>
        </div>
      </div>
    </div>`).join('');

  document.getElementById('cards').innerHTML = cards;
}
