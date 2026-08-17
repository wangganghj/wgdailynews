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

  let lastScrollY = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
  let isTicking = false;

  function handleScroll() {
    const currentScrollY = Math.max(0, window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0);
    const scrollDelta = currentScrollY - lastScrollY;

    // 当用户向下滚动且离开顶部区域时收起导航栏
    if (scrollDelta > 3 && currentScrollY > 30) {
      nav.classList.add('nav-hidden');
    } 
    // 当用户向上滚动或回到页面顶部时展开导航栏
    else if (scrollDelta < -5 || currentScrollY <= 15) {
      nav.classList.remove('nav-hidden');
    }

    lastScrollY = currentScrollY;
    isTicking = false;
  }

  window.addEventListener('scroll', () => {
    if (!isTicking) {
      window.requestAnimationFrame(handleScroll);
      isTicking = true;
    }
  }, { passive: true });

  // 移动端手指离开屏幕后，动量滚动可能继续触发
  window.addEventListener('touchend', () => {
    setTimeout(handleScroll, 50);
    setTimeout(handleScroll, 150);
  }, { passive: true });
})();
