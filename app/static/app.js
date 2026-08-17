const button = document.querySelector('#update-button');
const label = document.querySelector('#update-label');
const panel = document.querySelector('#progress-panel');
const bar = document.querySelector('#progress-bar');
const progressText = document.querySelector('#progress-text');

function renderProgress(progress) {
  const total = progress.total || 1;
  const percentage = Math.round(((progress.completed || 0) / total) * 100);
  bar.style.width = `${percentage}%`;
  const active = Object.values(progress.active || {})
    .map((item) => `${item.name}：${item.phase}`)
    .join('；');
  progressText.textContent = `${percentage}% · ${active || progress.phase || '准备更新'}`;
  panel.hidden = false;
}

async function poll() {
  const response = await fetch('/api/status');
  const data = await response.json();
  renderProgress(data.progress || {});
  if (data.status === 'running') {
    setTimeout(poll, 1000);
    return;
  }
  bar.style.width = '100%';
  progressText.textContent = '100% · 更新完成';
  setTimeout(() => location.reload(), 500);
}

button.addEventListener('click', async () => {
  button.disabled = true;
  label.textContent = '更新中…';
  panel.hidden = false;
  bar.style.width = '0';
  progressText.textContent = '0% · 正在准备更新…';
  try {
    const response = await fetch('/api/update', { method: 'POST' });
    if (response.ok || response.status === 409) {
      setTimeout(poll, 500);
    } else {
      throw new Error('update failed');
    }
  } catch (error) {
    button.disabled = false;
    label.textContent = '更新失败，请重试';
    progressText.textContent = '更新启动失败，请重试';
  }
});

if (button.disabled) setTimeout(poll, 500);

// 导航栏滚动交互：向下滚动收起，向上滚动显示
(function initNavScroll() {
  const nav = document.querySelector('.source-nav');
  if (!nav) return;

  let lastScrollY = window.pageYOffset || document.documentElement.scrollTop;
  let isTicking = false;

  window.addEventListener('scroll', () => {
    if (!isTicking) {
      window.requestAnimationFrame(() => {
        const currentScrollY = Math.max(0, window.pageYOffset || document.documentElement.scrollTop);
        const scrollDelta = currentScrollY - lastScrollY;

        // 向下滚动超过阈值且不在页面顶部时隐藏导航栏
        if (scrollDelta > 6 && currentScrollY > 80) {
          nav.classList.add('nav-hidden');
        } else if (scrollDelta < -6 || currentScrollY <= 80) {
          // 向上滚动或回到顶部时显示导航栏
          nav.classList.remove('nav-hidden');
        }

        lastScrollY = currentScrollY;
        isTicking = false;
      });
      isTicking = true;
    }
  }, { passive: true });
})();
