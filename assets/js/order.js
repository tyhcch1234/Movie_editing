/* Movie_editing — 委託表單：驗證、委託單預覽、開 GitHub Issue、複製、下載 txt */
(function () {
  'use strict';

  const REPO = 'tyhcch1234/Movie_editing';
  const DRAFT_KEY = 'movie_editing_draft_v1';

  const $ = id => document.getElementById(id);
  const fields = {
    drive: $('drive'), duration: $('duration'), music: $('music'),
    email: $('email'), notes: $('notes')
  };
  const hints = { drive: $('driveHint'), duration: $('durHint'), music: $('musicHint'), email: $('emailHint') };
  const defaults = {};
  Object.keys(hints).forEach(k => { if (hints[k]) defaults[k] = hints[k].textContent; });

  const today = () => {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  };

  /* ---------------- validators ---------------- */
  function parseDuration(raw) {
    const v = String(raw || '').trim().toLowerCase().replace(/\s+/g, '');
    if (!v) return null;
    let sec = null, m;
    if ((m = v.match(/^(\d{1,2}):([0-5]\d)$/))) sec = +m[1] * 60 + +m[2];
    else if ((m = v.match(/^(\d{1,2})分(?:(\d{1,2})秒?)?$/))) sec = +m[1] * 60 + (+m[2] || 0);
    else if ((m = v.match(/^(\d{1,4})(s|sec|秒)$/))) sec = +m[1];
    else if ((m = v.match(/^(\d{1,3})(m|min|分|分鐘)$/))) sec = +m[1] * 60;
    else if ((m = v.match(/^(\d{1,3})$/))) sec = +m[1] * 60;
    if (sec === null) return null;
    if (sec < 20 || sec > 1800) return null;
    return sec;
  }
  const mmss = s => Math.floor(s / 60) + ':' + String(Math.round(s % 60)).padStart(2, '0');

  const isDrive = v => /^https?:\/\/(drive|docs)\.google\.com\//i.test(v.trim());
  const isYouTube = v => /^https?:\/\/([a-z0-9-]+\.)?(youtube\.com|youtu\.be)\//i.test(v.trim());
  const isEmail = v => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

  function setHint(key, msg, kind) {
    const el = hints[key];
    if (!el) return;
    el.textContent = msg || defaults[key] || '';
    el.className = 'hint' + (kind ? ' ' + kind : '');
    fields[key].classList.toggle('invalid', kind === 'err');
  }

  /* ---------------- state ---------------- */
  function state() {
    const dSec = parseDuration(fields.duration.value);
    return {
      drive: fields.drive.value.trim(),
      music: fields.music.value.trim(),
      email: fields.email.value.trim(),
      notes: fields.notes.value.trim(),
      durationSec: dSec,
      duration: dSec ? mmss(dSec) : '',
      date: today()
    };
  }

  function valid(s) {
    return isDrive(s.drive) && !!s.durationSec && isEmail(s.email) && (!s.music || isYouTube(s.music));
  }

  /* ---------------- ticket ---------------- */
  function paint() {
    const s = state();

    const tDur = $('tDur');
    tDur.textContent = s.duration ? s.duration : '未填';
    tDur.className = 'v' + (s.duration ? ' good' : ' empty');

    const tDrive = $('tDrive');
    tDrive.textContent = s.drive ? (isDrive(s.drive) ? '已連結 Drive ✓' : '唔似 Drive 連結') : '未填';
    tDrive.className = 'v' + (s.drive && isDrive(s.drive) ? ' good' : ' empty');

    const tMusic = $('tMusic');
    tMusic.textContent = s.music ? (isYouTube(s.music) ? 'YouTube 已連結 ✓' : '唔似 YouTube 連結') : '無（由我配）';
    tMusic.className = 'v' + (s.music && isYouTube(s.music) ? ' good' : ' empty');

    const tEmail = $('tEmail');
    tEmail.textContent = s.email ? (isEmail(s.email) ? s.email : '格式未啱') : '未填';
    tEmail.className = 'v' + (s.email && isEmail(s.email) ? ' good' : ' empty');

    $('tDate').textContent = s.date;
    $('ticketNo').textContent = 'ED-' + s.date.replace(/-/g, '').slice(2);

    $('submitBtn').disabled = !valid(s);
    return s;
  }

  /* ---------------- brief ---------------- */
  function brief(s) {
    return [
      '【剪片委託】' + s.date,
      '片長：' + (s.duration || '（未填）'),
      '素材 Drive：' + (s.drive || '（未填）'),
      '背景音樂：' + (s.music || '無，由你配'),
      '通知 Email：' + (s.email || '（未填）'),
      '其他要求：' + (s.notes || '無'),
      '',
      '完成規格：MP4 / H.264 + AAC / 跟素材解析度（最高 1080p）',
      '交片：2–3 個工作天，完成後 email 通知並上架 ' + location.origin.replace(/\/$/, '') + '/'
    ].join('\n');
  }

  function issueUrl(s) {
    const title = '[委託] ' + (s.duration || '?') + ' 剪片 — ' + s.date;
    const body = [
      '### 剪片委託',
      '',
      '| 項目 | 內容 |',
      '| --- | --- |',
      '| 片長 | **' + (s.duration || '（未填）') + '** |',
      '| 素材（Google Drive） | ' + (s.drive || '（未填）') + ' |',
      '| 背景音樂（YouTube） | ' + (s.music || '無，由剪片方配）') + ' |',
      '| 通知 Email | ' + (s.email || '（未填）') + ' |',
      '| 落單日 | ' + s.date + ' |',
      '',
      '**其他要求**',
      '',
      s.notes ? s.notes : '_無_',
      '',
      '---',
      '- [ ] 素材已設為「知道連結的人可檢視」',
      '- [ ] 已下載素材',
      '- [ ] 已剪接並輸出 1080p',
      '- [ ] 已上架作品庫 + 已 email 通知'
    ].join('\n');
    return 'https://github.com/' + REPO + '/issues/new?labels=edit-request'
      + '&title=' + encodeURIComponent(title)
      + '&body=' + encodeURIComponent(body);
  }

  /* ---------------- toast ---------------- */
  let toastTimer;
  function toast(msg) {
    const el = $('toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
  }

  /* ---------------- live validation ---------------- */
  fields.drive.addEventListener('input', () => {
    const v = fields.drive.value.trim();
    if (!v) setHint('drive');
    else if (!isDrive(v)) setHint('drive', '唔似 Google Drive 連結，要 drive.google.com 或者 docs.google.com。', 'err');
    else setHint('drive', '已連結 Drive ✓ 記得開「知道連結嘅人都可以檢視」。', 'ok');
  });

  fields.duration.addEventListener('input', () => {
    const v = fields.duration.value.trim();
    if (!v) setHint('duration');
    else if (!parseDuration(v)) setHint('duration', '格式唔啱：用「3:00」或者「3」。範圍 0:20 – 30:00。', 'err');
    else setHint('duration', '即係 ' + mmss(parseDuration(v)) + '（' + parseDuration(v) + ' 秒）', 'ok');
    document.querySelectorAll('#durChips .chip').forEach(c =>
      c.classList.toggle('on', parseDuration(v) === parseDuration(c.dataset.d)));
    saveDraft();
    paint();
  });

  fields.music.addEventListener('input', () => {
    const v = fields.music.value.trim();
    if (!v) setHint('music');
    else if (!isYouTube(v)) setHint('music', '要 YouTube 或者 youtu.be 連結。', 'err');
    else setHint('music', '已連結 YouTube ✓', 'ok');
  });

  fields.email.addEventListener('input', () => {
    const v = fields.email.value.trim();
    if (!v) setHint('email');
    else if (!isEmail(v)) setHint('email', 'Email 格式唔啱。', 'err');
    else setHint('email', '完成後會寄去呢個地址 ✓', 'ok');
  });

  ['drive', 'music', 'email', 'notes', 'duration'].forEach(k =>
    fields[k].addEventListener('input', () => { paint(); saveDraft(); }));

  document.getElementById('durChips').addEventListener('click', e => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    fields.duration.value = chip.dataset.d;
    fields.duration.dispatchEvent(new Event('input'));
  });

  /* ---------------- draft ---------------- */
  function saveDraft() {
    try {
      const d = {};
      Object.keys(fields).forEach(k => d[k] = fields[k].value);
      localStorage.setItem(DRAFT_KEY, JSON.stringify(d));
    } catch (e) { /* 私人模式就略過 */ }
  }
  function loadDraft() {
    try {
      const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}');
      Object.keys(fields).forEach(k => { if (typeof d[k] === 'string') fields[k].value = d[k]; });
      ['drive', 'duration', 'music', 'email'].forEach(k => fields[k].dispatchEvent(new Event('input')));
    } catch (e) { /* ignore */ }
  }

  /* ---------------- actions ---------------- */
  document.getElementById('orderForm').addEventListener('submit', e => {
    e.preventDefault();
    const s = paint();
    if (!valid(s)) {
      toast('仲有資料未填好，睇返上面紅字。');
      const bad = fields.drive.classList.contains('invalid') ? fields.drive : fields.duration;
      (bad || fields.drive).focus();
      return;
    }
    window.open(issueUrl(s), '_blank', 'noopener');
    $('ticketFoot').innerHTML =
      '已開 GitHub 新 issue 分頁，撳 <b>Submit new issue</b> 就存檔成功。<br>'
      + '想即刻開工：撳「複製委託單」貼落對話。';
    $('formNote').innerHTML =
      '新分頁開咗嘅話，撳 <b>Submit new issue</b> 就完成提交。分頁冇彈出？'
      + ' <a href="' + issueUrl(s) + '" target="_blank" rel="noopener">手動開單</a>。';
    toast('已開委託單，去 GitHub 撳 Submit new issue');
  });

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
      document.body.removeChild(ta);
      return ok;
    }
  }

  document.getElementById('copyBtn').addEventListener('click', async () => {
    const s = paint();
    if (!valid(s)) { toast('先填好四個資料，我先複製得完整。'); return; }
    const ok = await copyText(brief(s));
    toast(ok ? '委託單已複製，貼落對話就得' : '複製唔到，試下「下載 .txt」');
  });

  document.getElementById('saveBtn').addEventListener('click', () => {
    const s = paint();
    const blob = new Blob([brief(s)], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '剪片委託-' + s.date + '.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast('已下載委託單');
  });

  /* ---------------- init ---------------- */
  loadDraft();
  paint();
})();
