/* 答题页交互：倒计时 / localStorage 实时缓存 / 自动保存 / 防漏答
 *
 * 缓存为什么要做两层（localStorage + 后端）：
 *   localStorage 快，每次按键都能写，但换浏览器就丢；
 *   后端慢，每 15 秒一次，换设备打开能接着答。
 *   两者并存，任何一层失效都不至于让孩子白做一整张卷。
 */
(function () {
  const LS_KEY = () => 'gxsc_exam_' + window.EXAM.attemptId;

  function loadLocal() {
    try { return JSON.parse(localStorage.getItem(LS_KEY()) || '{}'); }
    catch (e) { return {}; }
  }
  function saveLocal(obj) {
    try { localStorage.setItem(LS_KEY(), JSON.stringify(obj)); } catch (e) { /* 隐私模式忽略 */ }
  }

  function collect() {
    const answers = {}, scratch = {};
    // 填空题：同一题的多个空用中文分号连接，与标准答案的存储格式一致
    const blanks = {};
    document.querySelectorAll('[data-blank]').forEach((el) => {
      const id = el.dataset.blank;
      const idx = parseInt(el.dataset.blankIdx || '0', 10);
      blanks[id] = blanks[id] || {};
      blanks[id][idx] = el.value.trim();
    });
    for (const id in blanks) {
      const parts = Object.keys(blanks[id]).sort((a, b) => a - b)
        .map((k) => blanks[id][k]);
      // 空格作为多空分隔的退化写法：统一成「；」
      answers[id] = parts.join('；');
    }
    document.querySelectorAll('[data-scratch]').forEach((el) => {
      scratch[el.dataset.scratch] = el.value;
    });
    return { answers, scratch };
  }

  function setChoice(id, val, label) {
    const q = document.querySelector('[data-choice="' + id + '"][value="' + CSS.escape(val) + '"]');
    if (q) q.checked = true;
    document.querySelectorAll('[data-choice="' + id + '"]').forEach((el) => {
      el.closest('.choice').classList.remove('picked');
    });
    if (q) q.closest('.choice').classList.add('picked');
  }

  function countDone(answers) {
    return Object.values(answers).filter((v) => String(v).replace(/；/g, '').trim() !== '').length;
  }

  function toast(msg) {
    const tip = document.getElementById('saveTip');
    tip.textContent = msg;
    tip.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => tip.classList.remove('show'), 1600);
  }

  async function pushServer(payload, silent) {
    try {
      const res = await fetch('/api/attempts/' + window.EXAM.attemptId + '/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      if (!silent) toast('已保存草稿');
    } catch (e) {
      if (!silent) toast('保存失败，答案已存在本机');
    }
  }

  function restore(obj) {
    const { answers = {}, scratch = {} } = obj;
    for (const id in answers) {
      const val = answers[id];
      if (val === undefined || val === null) continue;
      const parts = String(val).split(/[；;]/);
      const slots = Array.from(document.querySelectorAll('[data-blank="' + id + '"]'))
        .sort((a, b) => (parseInt(a.dataset.blankIdx, 10) || 0) - (parseInt(b.dataset.blankIdx, 10) || 0));
      if (slots.length) {
        slots.forEach((el, i) => { el.value = (parts[i] || '').trim(); });
        continue;
      }
      // 单选/判断题：值就是选项文本或 √/×
      const radio = document.querySelector('[data-choice="' + id + '"][value="' + CSS.escape(String(val)) + '"]');
      if (radio) { setChoice(id, String(val)); continue; }
      const jb = document.querySelector('[data-judge="' + id + '"][data-val="' + String(val) + '"]');
      if (jb) {
        document.querySelectorAll('[data-judge="' + id + '"]').forEach((b) => b.classList.remove('picked'));
        jb.classList.add('picked');
      }
    }
    for (const id in scratch) {
      const el = document.querySelector('[data-scratch="' + id + '"]');
      if (el) el.value = scratch[id] || '';
    }
  }

  function startClock(remain) {
    const clock = document.getElementById('clock');
    let left = remain;
    function tick() {
      if (left <= 0) { autoSubmit(); return; }
      const m = Math.floor(left / 60), s = left % 60;
      clock.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
      if (left <= 300) clock.classList.add('danger');
      left -= 1;
      setTimeout(tick, 1000);
    }
    tick();
    window.__remaining = () => left;
  }

  let submitting = false;
  async function doSubmit(auto) {
    if (submitting) return;
    const payload = collect();
    const unanswered = countUnanswered(payload.answers);
    if (!auto && unanswered > 0) {
      if (!confirm('还有 ' + unanswered + ' 题未作答，确定现在交卷吗？')) return;
    }
    submitting = true;
    payload.remaining_sec = window.__remaining ? window.__remaining() : null;
    try {
      await pushServer(payload, true);
      const res = await fetch('/api/attempts/' + window.EXAM.attemptId + '/submit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const body = await res.json().catch(() => ({}));
      // 云端台账同步失败不影响交卷（分数已经算好存好了），
      // 但要让家长知道"这份成绩还没进云端表"，而不是悄悄吞掉。
      const tc = body.tcloud || {};
      if (tc.skipped === false && tc.ok === false) {
        alert('成绩已保存，但同步到腾讯文档台账失败：\n'
              + (tc.error || '原因未知') + '\n可稍后在报告页点「补传台账」。');
      }
      localStorage.removeItem(LS_KEY());
      location.href = '/report/' + window.EXAM.attemptId;
    } catch (e) {
      alert('交卷失败：' + e.message + '\n答案已保存在本机，请稍后重试。');
      submitting = false;
    }
  }
  function autoSubmit() {
    if (submitting) return;
    alert('考试时间到，系统将自动交卷。');
    doSubmit(true);
  }
  function countUnanswered(answers) {
    const all = document.querySelectorAll('[data-item]');
    let miss = 0;
    all.forEach((q) => {
      const id = q.dataset.item;
      const v = String(answers[id] || '').replace(/；/g, '').trim();
      if (!v) miss += 1;
    });
    return miss;
  }

  window.bootExam = function () {
    // 恢复顺序：先取本机（最即时），再合并服务端（可能是上次在别的设备写的）
    const local = loadLocal();
    if (local.answers) restore(local);
    const server = { answers: window.EXAM.answers || {}, scratch: window.EXAM.scratch || {} };
    const total = Object.keys(server.answers).length
      + Object.keys(server.scratch).length;
    const localN = Object.keys(local.answers || {}).length
      + Object.keys(local.scratch || {}).length;
    if (total > localN) restore(server);

    document.getElementById('totalCnt').textContent = String(window.EXAM.totalQuestions);

    function refreshProgress() {
      const { answers } = collect();
      const done = countDone(answers);
      document.getElementById('doneCnt').textContent = String(done);
      const pct = window.EXAM.totalQuestions ? done / window.EXAM.totalQuestions * 100 : 0;
      document.getElementById('progBar').style.width = pct + '%';
      saveLocal({ answers, scratch: collect().scratch });
    }

    document.addEventListener('input', (e) => {
      if (e.target.matches('[data-blank], [data-scratch]')) refreshProgress();
    });
    document.addEventListener('change', (e) => {
      if (e.target.matches('[data-choice]')) {
        setChoice(e.target.dataset.choice, e.target.value);
        refreshProgress();
      }
    });
    document.addEventListener('click', (e) => {
      const jb = e.target.closest('[data-judge]');
      if (!jb) return;
      document.querySelectorAll('[data-judge="' + jb.dataset.judge + '"]')
        .forEach((b) => b.classList.remove('picked'));
      jb.classList.add('picked');
      // 判断题把 √/× 写进与 data-blank 同名的隐藏位，让 collect() 能统一取到
      let holder = document.querySelector('[data-blank="' + jb.dataset.judge + '"]');
      if (!holder) {
        holder = document.createElement('input');
        holder.type = 'hidden';
        holder.dataset.blank = jb.dataset.judge;
        document.getElementById('examForm').appendChild(holder);
      }
      holder.value = jb.dataset.val;
      refreshProgress();
    });

    refreshProgress();
    startClock(window.EXAM.remainingSec);

    document.getElementById('submitBtn').addEventListener('click', () => doSubmit(false));

    // 定时落库 + 离开页面前补一次，避免最后一个答案没保存
    setInterval(() => pushServer(collect(), true), 15000);
    window.addEventListener('beforeunload', () => pushServer(collect(), true));
  };
})();
