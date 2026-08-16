(() => {
  'use strict';

  // DOM Elements
  const button = document.querySelector('#update-button');
  const label = document.querySelector('#update-label');
  const panel = document.querySelector('#progress-panel');
  const bar = document.querySelector('#progress-bar');
  const progressText = document.querySelector('#progress-text');

  // Search & Filter Elements
  const searchInput = document.querySelector('#search-input');
  const searchClear = document.querySelector('#search-clear');
  const searchStat = document.querySelector('#search-result-stat');
  const matchCount = document.querySelector('#match-count');
  const resetSearchBtn = document.querySelector('#reset-search-btn');
  const categoryPills = document.querySelectorAll('.cat-pill');
  const sourceSections = document.querySelectorAll('.source');
  const sourceNavLinks = document.querySelectorAll('.source-nav a');

  // Theme & Font
  const themeToggle = document.querySelector('#theme-toggle');
  const fontToggle = document.querySelector('#font-toggle');
  const fontSizeLabel = document.querySelector('#font-size-label');

  // AI Briefing
  const toggleBriefingBtn = document.querySelector('#toggle-briefing-btn');
  const briefingBody = document.querySelector('#briefing-body');
  const toggleBriefingIcon = document.querySelector('#toggle-briefing-icon');
  const copyBriefingBtn = document.querySelector('#copy-briefing-btn');
  const ttsBriefingBtn = document.querySelector('#tts-briefing-btn');

  // Bookmarks
  const bookmarksBtn = document.querySelector('#bookmarks-btn');
  const bookmarksDrawer = document.querySelector('#bookmarks-drawer');
  const drawerBackdrop = document.querySelector('#drawer-backdrop');
  const closeBookmarksBtn = document.querySelector('#close-bookmarks-btn');
  const bookmarksCount = document.querySelector('#bookmarks-count');
  const drawerCount = document.querySelector('#drawer-count');
  const bookmarksList = document.querySelector('#bookmarks-list');
  const clearBookmarksBtn = document.querySelector('#clear-bookmarks-btn');
  const copyBookmarksBtn = document.querySelector('#copy-bookmarks-btn');

  // TTS Player
  const ttsPlayerBar = document.querySelector('#tts-player-bar');
  const playerTitle = document.querySelector('#player-title');
  const ttsPauseBtn = document.querySelector('#tts-pause-btn');
  const ttsStopBtn = document.querySelector('#tts-stop-btn');

  let currentCategory = 'all';
  let searchQuery = '';
  let bookmarks = JSON.parse(localStorage.getItem('news_bookmarks') || '[]');

  // ==========================================
  // 1. Theme Management (Light / Dark)
  // ==========================================
  function initTheme() {
    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    setTheme(savedTheme);
  }

  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const isDark = theme === 'dark';
    if (themeToggle) {
      themeToggle.querySelector('.theme-icon').textContent = isDark ? '☀️' : '🌙';
      themeToggle.querySelector('.btn-text').textContent = isDark ? '日间模式' : '夜间模式';
    }
  }

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      setTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  // ==========================================
  // 2. Font Size Adjustment
  // ==========================================
  const fontSizes = ['standard', 'large', 'xlarge'];
  const fontLabels = { standard: '标准', large: '中大', xlarge: '特大' };
  let currentFontIdx = 0;

  function initFontSize() {
    const saved = localStorage.getItem('font_size') || 'standard';
    currentFontIdx = Math.max(0, fontSizes.indexOf(saved));
    applyFontSize();
  }

  function applyFontSize() {
    const size = fontSizes[currentFontIdx];
    document.documentElement.classList.remove('font-large', 'font-xlarge');
    if (size === 'large') document.documentElement.classList.add('font-large');
    if (size === 'xlarge') document.documentElement.classList.add('font-xlarge');
    if (fontSizeLabel) fontSizeLabel.textContent = fontLabels[size];
    localStorage.setItem('font_size', size);
  }

  if (fontToggle) {
    fontToggle.addEventListener('click', () => {
      currentFontIdx = (currentFontIdx + 1) % fontSizes.length;
      applyFontSize();
    });
  }

  // ==========================================
  // 3. Instant Search & Category Filtering
  // ==========================================
  function applyFilters() {
    const query = searchQuery.trim().toLowerCase();
    let totalMatches = 0;

    sourceSections.forEach((section) => {
      const sectionCat = section.getAttribute('data-category');
      const catMatches = currentCategory === 'all' || sectionCat === currentCategory;

      if (!catMatches) {
        section.classList.add('hidden');
        return;
      }

      let sectionHasVisibleArticles = false;
      const articles = section.querySelectorAll('.headline-item, .card');

      articles.forEach((article) => {
        const title = (article.getAttribute('data-title') || '').toLowerCase();
        const titleZh = (article.getAttribute('data-title-zh') || '').toLowerCase();
        const summary = (article.getAttribute('data-summary') || '').toLowerCase();
        const summaryZh = (article.getAttribute('data-summary-zh') || '').toLowerCase();
        const sourceName = (article.getAttribute('data-source') || '').toLowerCase();

        const fullText = `${title} ${titleZh} ${summary} ${summaryZh} ${sourceName}`;
        const matched = !query || fullText.includes(query);

        if (matched) {
          article.classList.remove('hidden');
          sectionHasVisibleArticles = true;
          totalMatches++;
        } else {
          article.classList.add('hidden');
        }
      });

      if (sectionHasVisibleArticles) {
        section.classList.remove('hidden');
      } else {
        section.classList.add('hidden');
      }
    });

    // Update sticky nav visibility
    sourceNavLinks.forEach((link) => {
      const key = link.getAttribute('data-key');
      const section = document.getElementById(key);
      if (section && !section.classList.contains('hidden')) {
        link.classList.remove('hidden');
      } else {
        link.classList.add('hidden');
      }
    });

    // Update Search Stat Display
    if (query) {
      searchStat.hidden = false;
      matchCount.textContent = totalMatches;
      searchClear.hidden = false;
    } else {
      searchStat.hidden = true;
      searchClear.hidden = true;
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value;
      applyFilters();
    });
  }

  if (searchClear) {
    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      applyFilters();
      searchInput.focus();
    });
  }

  if (resetSearchBtn) {
    resetSearchBtn.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      currentCategory = 'all';
      categoryPills.forEach((p) => p.classList.toggle('active', p.getAttribute('data-cat') === 'all'));
      applyFilters();
    });
  }

  categoryPills.forEach((pill) => {
    pill.addEventListener('click', () => {
      categoryPills.forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      currentCategory = pill.getAttribute('data-cat');
      applyFilters();
    });
  });

  // ==========================================
  // 4. AI Briefing Expand/Collapse & Copy
  // ==========================================
  if (toggleBriefingBtn) {
    toggleBriefingBtn.addEventListener('click', () => {
      const isCollapsed = briefingBody.classList.toggle('collapsed');
      toggleBriefingIcon.textContent = isCollapsed ? '▶' : '▼';
    });
  }

  if (copyBriefingBtn) {
    copyBriefingBtn.addEventListener('click', async () => {
      const date = document.querySelector('#briefing-date')?.textContent || '';
      const overview = document.querySelector('#briefing-overview')?.textContent || '';
      const cards = document.querySelectorAll('.briefing-point-card');
      
      let text = `📰 Daily News 全球早报速读 (${date})\n\n${overview}\n\n`;
      cards.forEach((card, i) => {
        const tag = card.querySelector('.point-tag')?.textContent || '';
        const title = card.querySelector('.point-title')?.textContent || '';
        const summary = card.querySelector('.point-summary')?.textContent || '';
        const sources = card.querySelector('.point-sources')?.textContent || '';
        text += `${i + 1}. [${tag}] ${title}\n   ${summary} (${sources})\n\n`;
      });

      try {
        await navigator.clipboard.writeText(text);
        const originalText = copyBriefingBtn.innerHTML;
        copyBriefingBtn.innerHTML = '<span>✅ 已复制</span>';
        setTimeout(() => { copyBriefingBtn.innerHTML = originalText; }, 2000);
      } catch (err) {
        alert('复制失败，请手动选取内容');
      }
    });
  }

  // ==========================================
  // 5. Bookmarks / Read Later Storage
  // ==========================================
  function saveBookmarks() {
    localStorage.setItem('news_bookmarks', JSON.stringify(bookmarks));
    updateBookmarkBadges();
    renderBookmarksDrawer();
  }

  function updateBookmarkBadges() {
    const count = bookmarks.length;
    if (bookmarksCount) bookmarksCount.textContent = count;
    if (drawerCount) drawerCount.textContent = count;

    // Update active states on cards
    const bookmarkedUrls = new Set(bookmarks.map((b) => b.url));
    document.querySelectorAll('.headline-item, .card').forEach((el) => {
      const url = el.getAttribute('data-url');
      const favBtn = el.querySelector('.btn-fav');
      if (favBtn) {
        favBtn.classList.toggle('active', bookmarkedUrls.has(url));
      }
    });
  }

  function toggleBookmark(articleData) {
    const idx = bookmarks.findIndex((b) => b.url === articleData.url);
    if (idx >= 0) {
      bookmarks.splice(idx, 1);
    } else {
      bookmarks.unshift({
        url: articleData.url,
        title: articleData.title,
        title_zh: articleData.title_zh,
        source: articleData.source,
        savedAt: new Date().toLocaleDateString(),
      });
    }
    saveBookmarks();
  }

  function renderBookmarksDrawer() {
    if (!bookmarksList) return;
    if (bookmarks.length === 0) {
      bookmarksList.innerHTML = '<div class="bookmark-empty">暂无收藏文章。<br>点击文章卡片右上角的 ⭐ 即可加入收藏。</div>';
      return;
    }

    bookmarksList.innerHTML = bookmarks
      .map(
        (b, i) => `
      <div class="bookmark-item">
        <a href="${b.url}" class="bookmark-item-title" target="_blank" rel="noopener noreferrer">${b.title}</a>
        ${b.title_zh ? `<div class="bookmark-item-zh">${b.title_zh}</div>` : ''}
        <div class="bookmark-item-meta">
          <span>${b.source || '新闻'} · ${b.savedAt}</span>
          <button class="btn-link remove-bm" data-index="${i}">移除</button>
        </div>
      </div>
    `
      )
      .join('');

    bookmarksList.querySelectorAll('.remove-bm').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.getAttribute('data-index'), 10);
        bookmarks.splice(idx, 1);
        saveBookmarks();
      });
    });
  }

  // Article Action Listeners (Delegated)
  document.addEventListener('click', (e) => {
    const favBtn = e.target.closest('.btn-fav');
    if (favBtn) {
      const article = favBtn.closest('.headline-item, .card');
      if (article) {
        toggleBookmark({
          url: article.getAttribute('data-url'),
          title: article.getAttribute('data-title'),
          title_zh: article.getAttribute('data-title-zh'),
          source: article.getAttribute('data-source'),
        });
      }
    }

    const speakBtn = e.target.closest('.btn-speak');
    if (speakBtn) {
      const article = speakBtn.closest('.headline-item, .card');
      if (article) {
        const titleZh = article.getAttribute('data-title-zh') || article.getAttribute('data-title');
        const summaryZh = article.getAttribute('data-summary-zh') || article.getAttribute('data-summary');
        const sourceName = article.getAttribute('data-source') || '';
        speakText(`${sourceName}。${titleZh}。${summaryZh}`, titleZh);
      }
    }
  });

  if (bookmarksBtn) {
    bookmarksBtn.addEventListener('click', () => {
      bookmarksDrawer.hidden = false;
      drawerBackdrop.hidden = false;
      renderBookmarksDrawer();
    });
  }

  if (closeBookmarksBtn) {
    closeBookmarksBtn.addEventListener('click', () => {
      bookmarksDrawer.hidden = true;
      drawerBackdrop.hidden = true;
    });
  }

  if (drawerBackdrop) {
    drawerBackdrop.addEventListener('click', () => {
      bookmarksDrawer.hidden = true;
      drawerBackdrop.hidden = true;
    });
  }

  if (clearBookmarksBtn) {
    clearBookmarksBtn.addEventListener('click', () => {
      if (confirm('确定要清空所有收藏吗？')) {
        bookmarks = [];
        saveBookmarks();
      }
    });
  }

  if (copyBookmarksBtn) {
    copyBookmarksBtn.addEventListener('click', async () => {
      if (!bookmarks.length) return;
      const text = bookmarks.map((b) => `- [${b.title_zh || b.title}](${b.url}) (${b.source})`).join('\n');
      await navigator.clipboard.writeText(text);
      alert('已复制所有收藏链接至剪贴板');
    });
  }

  // ==========================================
  // 6. Web Speech API (TTS 语音朗读)
  // ==========================================
  let synth = window.speechSynthesis;
  let currentUtterance = null;

  function speakText(text, displayLabel) {
    if (!synth) {
      alert('您的浏览器不支持语音播报功能');
      return;
    }
    synth.cancel();

    currentUtterance = new SpeechSynthesisUtterance(text);
    currentUtterance.lang = 'zh-CN';
    currentUtterance.rate = 1.05;

    // Pick best Chinese voice if available
    const voices = synth.getVoices();
    const zhVoice = voices.find((v) => v.lang.includes('zh') || v.lang.includes('cmn'));
    if (zhVoice) currentUtterance.voice = zhVoice;

    if (ttsPlayerBar) {
      ttsPlayerBar.hidden = false;
      playerTitle.textContent = displayLabel || '正在朗读新闻…';
      ttsPauseBtn.textContent = '⏸';
    }

    currentUtterance.onend = () => {
      if (ttsPlayerBar) ttsPlayerBar.hidden = true;
    };
    currentUtterance.onerror = () => {
      if (ttsPlayerBar) ttsPlayerBar.hidden = true;
    };

    synth.speak(currentUtterance);
  }

  if (ttsBriefingBtn) {
    ttsBriefingBtn.addEventListener('click', () => {
      const overview = document.querySelector('#briefing-overview')?.textContent || '';
      const cards = document.querySelectorAll('.briefing-point-card');
      let text = `今日全球要闻核心综述。${overview}。`;
      cards.forEach((card, i) => {
        const title = card.querySelector('.point-title')?.textContent || '';
        const summary = card.querySelector('.point-summary')?.textContent || '';
        text += `第${i + 1}条，${title}。${summary}。`;
      });
      speakText(text, '今日 AI 全球早报速读');
    });
  }

  if (ttsPauseBtn) {
    ttsPauseBtn.addEventListener('click', () => {
      if (!synth) return;
      if (synth.speaking) {
        if (synth.paused) {
          synth.resume();
          ttsPauseBtn.textContent = '⏸';
        } else {
          synth.pause();
          ttsPauseBtn.textContent = '▶';
        }
      }
    });
  }

  if (ttsStopBtn) {
    ttsStopBtn.addEventListener('click', () => {
      if (synth) synth.cancel();
      if (ttsPlayerBar) ttsPlayerBar.hidden = true;
    });
  }

  // ==========================================
  // 7. Update Polling
  // ==========================================
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
    try {
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
    } catch (e) {
      setTimeout(poll, 2000);
    }
  }

  if (button) {
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
  }

  if (button && button.disabled) setTimeout(poll, 500);

  // Initialize
  initTheme();
  initFontSize();
  updateBookmarkBadges();
})();
