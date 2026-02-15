let defaultCodes = [];
let latestPortfolioPositions = [];
let currentMarket = 'cn';
let currentView = 'holdings';
let currentFundDetail = null;
let latestEstimateResults = [];
let autoRefreshTimer = null;
let isMarketRefreshing = false;
let previousIndexMap = {};
let previousGoldMap = {};
let marketLoadedOnce = false;

function asNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function formatPercent(v, digits = 2) {
  return `${asNumber(v).toFixed(digits)}%`;
}

function formatAmount(v) {
  const n = asNumber(v);
  const abs = Math.abs(n);
  if (abs >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(n / 1e4).toFixed(2)}万`;
  return n.toFixed(2);
}

function formatSigned(v, digits = 2) {
  const n = asNumber(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}`;
}

function numberClass(v) {
  return asNumber(v) >= 0 ? 'up' : 'down';
}


const THEME_KEY = 'fund_terminal_theme';

function applyTheme(theme) {
  const nextTheme = theme === 'light' ? 'light' : 'dark';
  document.body.dataset.theme = nextTheme;
  const btn = document.getElementById('themeToggleBtn');
  if (btn) btn.innerText = nextTheme === 'dark' ? '切换浅色' : '切换深色';
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  applyTheme(stored || 'dark');
}

function toggleTheme() {
  const current = document.body.dataset.theme === 'light' ? 'light' : 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
}


function getFlashClass(prevValue, nextValue) {
  const prev = Number(prevValue);
  const next = Number(nextValue);
  if (!Number.isFinite(prev) || !Number.isFinite(next) || prev === next) return '';
  return next > prev ? 'flash-up' : 'flash-down';
}

function toggleAutoRefresh(enabled) {
  const autoRefreshToggle = document.getElementById('autoRefreshToggle');
  if (autoRefreshToggle && autoRefreshToggle.checked !== enabled) {
    autoRefreshToggle.checked = enabled;
  }
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
  if (enabled && currentView === 'market') {
    autoRefreshTimer = setInterval(() => {
      refreshMarketAndGold();
    }, 10000);
  }
}

function setLoading(buttonId, loading, loadingText) {
  const btn = document.getElementById(buttonId);
  if (!btn) return;
  if (!btn.dataset.originText) btn.dataset.originText = btn.innerText;
  btn.disabled = loading;
  btn.innerText = loading ? loadingText : btn.dataset.originText;
}

function showToast(message) {
  const area = document.getElementById('toastArea');
  if (!area || !message) return;
  const item = document.createElement('div');
  item.className = 'toast';
  item.innerText = message;
  area.appendChild(item);
  setTimeout(() => item.remove(), 5000);
}

function renderKpi({ estimatePnl = null, totalAsset = null, positions = 0, timeText = '—' } = {}) {
  const estimateEl = document.getElementById('kpiEstimatePnl');
  const assetsEl = document.getElementById('kpiAssets');
  const positionsEl = document.getElementById('kpiPositions');
  const refreshEl = document.getElementById('kpiRefresh');
  if (estimateEl) estimateEl.innerText = estimatePnl === null ? '—' : formatAmount(estimatePnl);
  if (assetsEl) assetsEl.innerText = totalAsset === null ? '—' : formatAmount(totalAsset);
  if (positionsEl) positionsEl.innerText = String(positions);
  if (refreshEl) refreshEl.innerText = timeText;
}

async function loadHealthStatus() {
  try {
    const resp = await fetch('/api/health');
    const data = await resp.json();
    const parts = [
      data.index_provider ? `INDEX:${String(data.index_provider).toUpperCase()}` : null,
      data.gold_provider ? `GOLD:${String(data.gold_provider).toUpperCase()}` : null,
      data.quote_provider ? `QUOTE:${String(data.quote_provider).toUpperCase()}` : null,
      data.holdings_provider ? `HOLD:${String(data.holdings_provider).toUpperCase()}` : null,
    ].filter(Boolean);
    document.getElementById('providerStatus').innerText = parts.length ? parts.join(' · ') : 'DATA: AUTO';
    if (data.mode === 'stdlib') {
      const limitedText = '受限模式：数据源为 mock/部分功能降级';
      document.getElementById('msg').innerText = limitedText;
      showToast(limitedText);
    }
  } catch (_) {
    document.getElementById('providerStatus').innerText = 'DATA: AUTO';
  }
}

async function bootstrap() {
  initTheme();
  const autoRefreshToggle = document.getElementById('autoRefreshToggle');
  if (autoRefreshToggle) autoRefreshToggle.checked = false;
  toggleAutoRefresh(false);
  await loadDefaultCodes();
  await loadHealthStatus();
  await loadPortfolio();
  renderAssetsSummary();

  const initialView = normalizeViewFromHash(location.hash);
  switchView(initialView || 'holdings', { updateHash: true });
  window.addEventListener('hashchange', () => {
    const view = normalizeViewFromHash(location.hash);
    switchView(view || 'holdings', { updateHash: false });
  });
}

function normalizeViewFromHash(hash) {
  const raw = String(hash || '').replace('#', '').trim().toLowerCase();
  if (['assets', 'holdings', 'market'].includes(raw)) return raw;
  return 'holdings';
}

function switchView(viewName, options = {}) {
  const nextView = ['assets', 'holdings', 'market'].includes(viewName) ? viewName : 'holdings';
  currentView = nextView;

  document.querySelectorAll('#mainTabs .tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === nextView);
  });
  document.querySelectorAll('.view').forEach(view => {
    view.classList.toggle('active', view.id === `view-${nextView}`);
  });

  if (options.updateHash !== false && location.hash !== `#${nextView}`) {
    location.hash = `#${nextView}`;
  }

  if (nextView === 'market') {
    if (!marketLoadedOnce) {
      refreshMarketAndGold();
      marketLoadedOnce = true;
    }
    const autoRefreshToggle = document.getElementById('autoRefreshToggle');
    toggleAutoRefresh(Boolean(autoRefreshToggle && autoRefreshToggle.checked));
  } else {
    toggleAutoRefresh(false);
  }

  if (nextView === 'assets') {
    renderAssetsSummary();
  }
}

async function loadDefaultCodes() {
  try {
    const resp = await fetch('/api/default-codes');
    const data = await resp.json();
    defaultCodes = data.codes || [];
  } catch (_) {
    defaultCodes = [];
  }
}

async function fetchPortfolio(activeOnly = 1) {
  try {
    const resp = await fetch(`/api/portfolio?active_only=${activeOnly}`);
    return await resp.json();
  } catch (_) {
    return { positions: [], updated_at: 0 };
  }
}

function initPortfolio(codes) {
  const positions = codes.map(code => ({ code, name: '', share: 0, cost: 0, current_profit: 0, is_active: 1 }));
  initPortfolioFromPositions(positions);
}

function positionRowHtml(p) {
  const isActive = asNumber(p.is_active || 1) === 1;
  return `<td><input class='code' value='${p.code || ''}'/></td>
    <td><input class='name' value='${p.name || ''}'/></td>
    <td><input type='number' class='share t-right' step='0.01' value='${asNumber(p.share)}'/></td>
    <td><input type='number' class='cost t-right' step='0.0001' value='${asNumber(p.cost)}'/></td>
    <td><input type='number' class='profit t-right' step='0.01' value='${asNumber(p.current_profit)}'/></td>
    <td class='status'>${isActive ? '活跃' : '已归档'}</td>
    <td>
      <button type='button' onclick='toggleArchiveRow(this)'>${isActive ? '归档' : '恢复'}</button>
      <button type='button' onclick='deleteRow(this)'>删除</button>
    </td>`;
}

function addPositionRow() {
  const tb = document.querySelector('#portfolio tbody');
  const tr = document.createElement('tr');
  tr.dataset.active = '1';
  tr.innerHTML = positionRowHtml({ code: '', name: '', share: 0, cost: 0, current_profit: 0, is_active: 1 });
  tb.appendChild(tr);
}

function initPortfolioFromPositions(positions) {
  const tb = document.querySelector('#portfolio tbody');
  tb.innerHTML = '';
  positions.forEach(p => {
    const tr = document.createElement('tr');
    tr.dataset.active = String(asNumber(p.is_active || 1) === 1 ? 1 : 0);
    tr.innerHTML = positionRowHtml(p);
    tb.appendChild(tr);
  });
}

function readPortfolio() {
  const list = [];
  document.querySelectorAll('#portfolio tbody tr').forEach(tr => {
    const code = tr.querySelector('.code').value.trim();
    if (!code) return;
    list.push({
      code,
      name: tr.querySelector('.name').value.trim(),
      share: asNumber(tr.querySelector('.share').value),
      cost: asNumber(tr.querySelector('.cost').value),
      current_profit: asNumber(tr.querySelector('.profit').value),
      is_active: asNumber(tr.dataset.active || 1) === 1 ? 1 : 0,
    });
  });
  return list;
}

async function refreshPortfolioUI(msg = '') {
  const portfolio = await fetchPortfolio(1);
  latestPortfolioPositions = portfolio.positions || [];
  initPortfolioFromPositions(portfolio.positions);
  document.getElementById('codes').value = portfolio.positions.map(p => p.code).join(' ');
  if (msg) document.getElementById('msg').innerText = msg;
  renderKpi({ positions: portfolio.positions.length, timeText: new Date().toLocaleTimeString() });
  renderAssetsSummary();
}

async function loadPortfolio() {
  const portfolioResp = await fetchPortfolio();
  latestPortfolioPositions = portfolioResp.positions || [];

  if (portfolioResp.positions.length > 0) {
    document.getElementById('codes').value = portfolioResp.positions.map(p => p.code).join(' ');
    initPortfolioFromPositions(portfolioResp.positions);
    document.getElementById('msg').innerText = '已加载已保存持仓';
  } else {
    document.getElementById('codes').value = defaultCodes.join(' ');
    initPortfolio(defaultCodes);
    latestPortfolioPositions = defaultCodes.map(code => ({ code, share: 0, cost: 0, current_profit: 0 }));
    document.getElementById('msg').innerText = '暂无已保存持仓，可点击“从输入导入到持仓”';
  }

  renderKpi({ positions: portfolioResp.positions.length, timeText: new Date().toLocaleTimeString() });
}

async function syncPortfolio() {
  const codes = document.getElementById('codes').value.split(/[\s,，]+/).filter(Boolean);
  const resp = await fetch('/api/portfolio/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codes }),
  });
  const data = await resp.json();
  await refreshPortfolioUI(data.ok ? `导入完成：${data.count} 条` : '导入失败');
}

async function savePortfolio() {
  const positions = readPortfolio();
  const resp = await fetch('/api/portfolio/positions/bulk_upsert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ positions }),
  });
  const data = await resp.json();
  await refreshPortfolioUI(data.ok ? `保存完成：${data.count} 条` : '保存失败');
}

async function toggleArchiveRow(btn) {
  const tr = btn.closest('tr');
  const code = tr?.querySelector('.code')?.value?.trim() || '';
  if (!code) {
    showToast('请先填写代码并保存');
    return;
  }
  const currentActive = asNumber(tr.dataset.active || 1) === 1;
  const endpoint = currentActive ? 'archive' : 'activate';
  const resp = await fetch(`/api/portfolio/positions/${encodeURIComponent(code)}/${endpoint}`, { method: 'POST' });
  const data = await resp.json();
  await refreshPortfolioUI(data.ok ? `${code} 已${currentActive ? '归档' : '恢复'}` : '操作失败');
}

async function deleteRow(btn) {
  const tr = btn.closest('tr');
  const code = tr?.querySelector('.code')?.value?.trim() || '';
  if (!code) {
    tr.remove();
    return;
  }
  const resp = await fetch(`/api/portfolio/positions/${encodeURIComponent(code)}`, { method: 'DELETE' });
  const data = await resp.json();
  await refreshPortfolioUI(data.ok ? `${code} 已删除` : '删除失败');
}

function switchMarket(market) {
  currentMarket = market;
  document.querySelectorAll('#marketTabs .tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.market === market);
  });
  const indexSection = document.getElementById('indexSection');
  const goldSection = document.getElementById('goldSection');
  const showGold = market === 'gold';
  if (indexSection) indexSection.classList.toggle('hidden', showGold);
  if (goldSection) goldSection.classList.toggle('hidden', !showGold);
  if (showGold) {
    loadGoldQuotes();
  } else {
    loadIndexes(market);
  }
}

async function refreshMarketAndGold() {
  if (isMarketRefreshing) return;
  isMarketRefreshing = true;
  setLoading('refreshBtn', true, '刷新中...');
  try {
    if (currentMarket === 'gold') {
      await loadGoldQuotes();
    } else {
      await Promise.all([loadIndexes(currentMarket), loadGoldQuotes()]);
    }
    renderKpi({
      estimatePnl: latestEstimateResults.reduce((acc, x) => acc + asNumber(x.estimatePnL), 0),
      totalAsset: null,
      positions: document.querySelectorAll('#portfolio tbody tr').length,
      timeText: new Date().toLocaleTimeString(),
    });
  } finally {
    setLoading('refreshBtn', false, '刷新指数与黄金');
    isMarketRefreshing = false;
  }
}

function renderAssetsSummary() {
  const positions = latestPortfolioPositions || [];
  const totalCost = positions.reduce((acc, p) => acc + asNumber(p.share) * asNumber(p.cost), 0);
  const holdingProfit = positions.reduce((acc, p) => acc + asNumber(p.current_profit), 0);
  const totalAssetEstimate = positions.length ? totalCost + holdingProfit : null;
  const todayEstimate = latestEstimateResults.length
    ? latestEstimateResults.reduce((acc, x) => acc + asNumber(x.estimatePnL), 0)
    : null;

  const setValue = (id, value) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerText = value === null ? '—' : formatAmount(value);
  };

  setValue('assetTotalAsset', totalAssetEstimate);
  setValue('assetTodayEstimate', todayEstimate);
  setValue('assetTotalCost', positions.length ? totalCost : null);

  const yesterdayEl = document.getElementById('assetYesterdayPnl');
  if (yesterdayEl) yesterdayEl.innerText = '—';
  const realizedEl = document.getElementById('assetRealizedPnl');
  if (realizedEl) realizedEl.innerText = '—';
}

const assetsPlaceholderText = {
  totalAssets: '阶段2将展示总资产历史曲线、资产组成分布与日内变化明细。',
  yesterdayPnl: '阶段2将接入收益快照并展示昨日收益拆解。',
  todayEstimate: '阶段2将展示今日预估收益按基金明细与贡献排行。',
  realizedPnl: '阶段4将接入交易流水，展示已实现收益与卖出明细。',
  totalCost: '阶段2将展示总成本历史变化与分批投入记录。',
};

function openAssetsPlaceholder(type) {
  const titleMap = {
    totalAssets: '总资产（估算）',
    yesterdayPnl: '昨日收益',
    todayEstimate: '今日预估收益',
    realizedPnl: '已实现收益',
    totalCost: '总成本 / 总投入',
  };
  document.getElementById('placeholderTitle').innerText = titleMap[type] || '指标详情';
  document.getElementById('placeholderBody').innerText = assetsPlaceholderText[type] || '阶段2将展示历史曲线/明细。';
  document.getElementById('placeholderModalMask').style.display = 'flex';
}

function closePlaceholderModal(event) {
  if (event && event.target && event.target.id !== 'placeholderModalMask') return;
  document.getElementById('placeholderModalMask').style.display = 'none';
}

async function loadIndexes(market) {
  const container = document.getElementById('indexCards');
  container.innerHTML = '<div class="muted">加载中...</div>';
  try {
    const resp = await fetch(`/api/indexes?market=${encodeURIComponent(market)}`);
    const data = await resp.json();
    container.innerHTML = '';
    const nextMap = {};
    (data.quotes || []).forEach(q => {
      const row = document.createElement('div');
      const cls = numberClass(q.change_percent);
      const prev = previousIndexMap[q.code] || {};
      const currentFlash = getFlashClass(prev.current, q.current);
      const pctFlash = getFlashClass(prev.change_percent, q.change_percent);
      const valueFlash = getFlashClass(prev.change_value, q.change_value);
      row.className = 'ticker-row';
      row.innerHTML = `<div>${q.name} <span class='muted'>${q.code}</span></div>
        <div class='t-right ${currentFlash}'>${asNumber(q.current).toFixed(2)}</div>
        <div class='t-right ${cls} ${pctFlash}'>${formatPercent(q.change_percent)}</div>
        <div class='t-right ${cls} ${valueFlash}'>${formatSigned(q.change_value)}</div>`;
      container.appendChild(row);
      nextMap[q.code] = { current: q.current, change_percent: q.change_percent, change_value: q.change_value };
    });
    previousIndexMap = nextMap;
  } catch (_) {
    container.innerHTML = '<div class="muted">指数加载失败</div>';
    showToast('指数加载失败，请稍后重试');
  }
}

async function loadGoldQuotes() {
  const container = document.getElementById('goldCards');
  container.innerHTML = '<tr><td colspan="4" class="muted">加载中...</td></tr>';
  try {
    const resp = await fetch('/api/gold/realtime');
    const data = await resp.json();
    container.innerHTML = '';
    const nextMap = {};
    (data.quotes || []).forEach(q => {
      const cls = numberClass(q.change_percent);
      const prev = previousGoldMap[q.platform] || {};
      const priceFlash = getFlashClass(prev.price, q.price);
      const changeFlash = getFlashClass(prev.change, q.change);
      const pctFlash = getFlashClass(prev.change_percent, q.change_percent);
      const tr = document.createElement('tr');
      tr.innerHTML = `<td class='t-left'>${q.platform}</td>
        <td class='t-right ${priceFlash}'>${asNumber(q.price).toFixed(2)}</td>
        <td class='t-right ${cls} ${changeFlash}'>${formatSigned(q.change)}</td>
        <td class='t-right ${cls} ${pctFlash}'>${formatPercent(q.change_percent)}</td>`;
      container.appendChild(tr);
      nextMap[q.platform] = { price: q.price, change: q.change, change_percent: q.change_percent };
    });
    previousGoldMap = nextMap;
  } catch (_) {
    container.innerHTML = '<tr><td colspan="4" class="muted">黄金报价加载失败</td></tr>';
    showToast('黄金报价加载失败，请稍后重试');
  }
}

async function runEstimate() {
  const portfolioResp = await fetchPortfolio(1);
  const codes = (portfolioResp.positions || []).map(p => p.code).filter(Boolean);
  const portfolioMap = {};
  portfolioResp.positions.forEach(p => { portfolioMap[p.code] = p; });

  document.getElementById('codes').value = codes.join(' ');
  document.getElementById('msg').innerText = '抓取中，请稍候...';
  setLoading('estimateBtn', true, '估值抓取中...');

  try {
    const resp = await fetch(`/api/estimate?codes=${encodeURIComponent(codes.join(','))}`);
    const data = await resp.json();

    if ((data.failures || []).length) {
      const text = `部分失败: ${data.failures.join(' | ')}`;
      document.getElementById('msg').innerText = text;
      showToast(text);
    } else {
      document.getElementById('msg').innerText = '抓取完成';
    }

    const summaryDiv = document.getElementById('summary');
    summaryDiv.innerHTML = '';
    let html = '<table><thead><tr><th class="t-left">基金代码</th><th class="t-left">基金名称</th><th class="t-left">披露期</th><th class="t-left">持仓源</th><th class="t-right">预估涨跌</th><th class="t-right">行情覆盖权重</th><th class="t-right">当前持有收益</th><th class="t-right">预估当日盈亏</th><th class="t-left">操作</th></tr></thead><tbody>';

    latestEstimateResults = (data.results || []).map(r => {
      const p = portfolioMap[r.code] || { share: 0, cost: 0, current_profit: 0 };
      const estimatePnL = asNumber(p.share) * asNumber(p.cost) * (asNumber(r.estimated_pct) / 100);
      return { ...r, estimatePnL };
    });

    latestEstimateResults.forEach(r => {
      const pnlClass = numberClass(r.estimatePnL);
      const pctClass = numberClass(r.estimated_pct);
      html += `<tr onclick="openFundDetail('${r.code}')" class='clickable-row'><td class='t-left'>${r.code}</td><td class='t-left'>${r.name}</td><td class='t-left'>${r.report_period}</td><td class='t-left'>${r.source}</td>
      <td class='t-right ${pctClass}'>${formatPercent(r.estimated_pct)}</td><td class='t-right'>${formatPercent(r.matched_weight)}</td>
      <td class='t-right'>${formatAmount((portfolioMap[r.code] || {}).current_profit || 0)}</td><td class='t-right ${pnlClass}'>${formatAmount(r.estimatePnL)}</td>
      <td><button onclick="event.stopPropagation();openFundDetail('${r.code}')">详情</button></td></tr>`;
    });

    html += '</tbody></table>';
    summaryDiv.innerHTML = html;

    const detailDiv = document.getElementById('details');
    detailDiv.innerHTML = '';
    latestEstimateResults.forEach(r => {
      let inner = '';
      if ((r.missing_symbols || []).length) {
        inner += `<p class='muted'>以下成分未匹配行情，按 0% 处理：${r.missing_symbols.join(', ')}</p>`;
      }
      inner += '<table><thead><tr><th class="t-left">代码</th><th class="t-left">名称</th><th class="t-right">权重</th><th class="t-right">实时涨跌</th><th class="t-right">贡献</th></tr></thead><tbody>';
      (r.details || []).forEach(x => {
        inner += `<tr><td>${x.symbol}</td><td>${x.name}</td><td class='t-right'>${asNumber(x.weight).toFixed(2)}%</td><td class='t-right ${numberClass(x.change)}'>${formatPercent(x.change)}</td><td class='t-right ${numberClass(x.contribution)}'>${formatPercent(x.contribution)}</td></tr>`;
      });
      inner += '</tbody></table>';

      const d = document.createElement('details');
      d.innerHTML = `<summary>${r.name}（${r.code}） | 预估 ${formatPercent(r.estimated_pct)} | 披露期: ${r.report_period} | 源: ${r.source}</summary>${inner}`;
      detailDiv.appendChild(d);
    });

    const totalPnl = latestEstimateResults.reduce((acc, x) => acc + asNumber(x.estimatePnL), 0);
    renderKpi({
      estimatePnl: totalPnl,
      totalAsset: null,
      positions: portfolioResp.positions.length,
      timeText: new Date().toLocaleTimeString(),
    });
    renderAssetsSummary();
  } catch (_) {
    showToast('估值抓取失败，请稍后重试');
  } finally {
    setLoading('estimateBtn', false, '抓取并预估');
  }
}

function switchDetailTab(tab) {
  ['history', 'stage', 'nav', 'holding'].forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    if (el) el.classList.toggle('active', t === tab);
    document.querySelectorAll('[data-detail-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.detailTab === tab);
    });
  });
  if (tab === 'nav' && currentFundDetail) {
    renderNavCanvas(currentFundDetail.nav_history || []);
  }
}

function closeFundDetail(event) {
  if (event && event.target && event.target.id !== 'detailModalMask') return;
  document.getElementById('detailModalMask').style.display = 'none';
}

async function openFundDetail(code) {
  const mask = document.getElementById('detailModalMask');
  mask.style.display = 'flex';
  document.getElementById('detailTitle').innerText = `基金详情 ${code}`;
  document.getElementById('detailMeta').innerText = '加载中...';

  const resp = await fetch(`/api/funds/${encodeURIComponent(code)}/detail`);
  const data = await resp.json();
  currentFundDetail = data;

  document.getElementById('detailTitle').innerText = `${data.code} · ${data.name}`;
  document.getElementById('detailMeta').innerText = `预估 ${formatPercent(data.estimated_pct)} | 覆盖权重 ${formatPercent(data.matched_weight)} | ${data.report_period} | ${data.source}`;

  document.getElementById('tab-history').innerHTML = `
    <p>基金代码：${data.code}</p>
    <p>基金名称：${data.name}</p>
    <p class='${numberClass(data.estimated_pct)}'>当前预估涨跌：${formatPercent(data.estimated_pct)}</p>
  `;

  let stageHtml = '<table><thead><tr><th class="t-left">区间</th><th class="t-right">基金收益</th><th class="t-right">同类均值</th><th class="t-right">业绩基准</th><th class="t-left">排名</th></tr></thead><tbody>';
  (data.stage_performance || []).forEach(s => {
    stageHtml += `<tr><td>${s.period}</td><td class='t-right ${numberClass(s.fund_return)}'>${formatPercent(s.fund_return)}</td><td class='t-right'>${formatPercent(s.category_avg)}</td><td class='t-right'>${formatPercent(s.benchmark)}</td><td>${s.rank}</td></tr>`;
  });
  stageHtml += '</tbody></table>';
  document.getElementById('tab-stage').innerHTML = stageHtml;

  let holdingHtml = '<table><thead><tr><th class="t-left">代码</th><th class="t-left">名称</th><th class="t-right">权重</th><th class="t-right">实时涨跌</th><th class="t-right">贡献</th></tr></thead><tbody>';
  (data.holdings || []).forEach(h => {
    holdingHtml += `<tr><td>${h.symbol}</td><td>${h.name}</td><td class='t-right'>${asNumber(h.weight).toFixed(2)}%</td><td class='t-right ${numberClass(h.change)}'>${formatPercent(h.change)}</td><td class='t-right ${numberClass(h.contribution)}'>${formatPercent(h.contribution)}</td></tr>`;
  });
  holdingHtml += '</tbody></table>';
  document.getElementById('tab-holding').innerHTML = holdingHtml;

  switchDetailTab('history');
}

function renderNavCanvas(rows) {
  const canvas = document.getElementById('navCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx || !rows || rows.length === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.width;
  const h = canvas.clientHeight || canvas.height;
  canvas.width = Math.max(1, Math.floor(w * dpr));
  canvas.height = Math.max(1, Math.floor(h * dpr));
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);

  const style = getComputedStyle(document.documentElement);
  const borderColor = style.getPropertyValue('--border').trim() || '#26344d';
  const lineColor = style.getPropertyValue('--up').trim() || '#35d07f';
  const textColor = style.getPropertyValue('--text1').trim() || '#b4c0d9';

  const pad = 28;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = borderColor;
  ctx.strokeRect(0, 0, w, h);

  const values = rows.map(r => asNumber(r.nav));
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const span = Math.max(0.0001, maxV - minV);

  ctx.beginPath();
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 2;
  rows.forEach((r, i) => {
    const x = pad + (w - pad * 2) * (i / (rows.length - 1 || 1));
    const y = h - pad - ((asNumber(r.nav) - minV) / span) * (h - pad * 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = textColor;
  ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, Consolas';
  ctx.fillText(minV.toFixed(4), 6, h - 8);
  ctx.fillText(maxV.toFixed(4), 6, 14);

  document.getElementById('navLegend').innerText = `区间: ${rows[0].date} ~ ${rows[rows.length - 1].date} | 最低 ${minV.toFixed(4)} | 最高 ${maxV.toFixed(4)}`;
}

window.addEventListener('beforeunload', () => toggleAutoRefresh(false));

bootstrap();
