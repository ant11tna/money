let defaultCodes = [];
let currentMarket = 'cn';
let currentFundDetail = null;

async function bootstrap() {
  await loadDefaultCodes();
  const portfolioResp = await fetchPortfolio();

  if (portfolioResp.positions.length > 0) {
    document.getElementById('codes').value = portfolioResp.positions.map(p => p.code).join(' ');
    initPortfolioFromPositions(portfolioResp.positions);
    document.getElementById('msg').innerText = '已加载已保存持仓';
  } else {
    document.getElementById('codes').value = defaultCodes.join(' ');
    initPortfolio(defaultCodes);
    document.getElementById('msg').innerText = '暂无已保存持仓，可点击“同步基金列表到持仓表”';
  }

  await refreshMarketAndGold();
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

async function fetchPortfolio() {
  try {
    const resp = await fetch('/api/portfolio');
    return await resp.json();
  } catch (_) {
    return { positions: [], updated_at: 0 };
  }
}

function initPortfolio(codes){
  const positions = codes.map(code => ({ code, name: '', share: 0, cost: 0, current_profit: 0 }));
  initPortfolioFromPositions(positions);
}

function initPortfolioFromPositions(positions){
  const tb=document.querySelector('#portfolio tbody');
  tb.innerHTML='';
  positions.forEach(p=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><input class='code' value='${p.code || ''}'/></td>
      <td><input type='number' class='share' step='0.01' value='${Number(p.share || 0)}'/></td>
      <td><input type='number' class='cost' step='0.0001' value='${Number(p.cost || 0)}'/></td>
      <td><input type='number' class='profit' step='0.01' value='${Number(p.current_profit || 0)}'/></td>`;
    tb.appendChild(tr);
  });
}

function readPortfolio(){
  const list=[];
  document.querySelectorAll('#portfolio tbody tr').forEach(tr=>{
    const code=tr.querySelector('.code').value.trim();
    if(!code) return;
    list.push({
      code,
      share: Number(tr.querySelector('.share').value||0),
      cost: Number(tr.querySelector('.cost').value||0),
      current_profit: Number(tr.querySelector('.profit').value||0),
    });
  });
  return list;
}

async function syncPortfolio(){
  const codes=document.getElementById('codes').value.split(/[\s,，]+/).filter(Boolean);
  const resp = await fetch('/api/portfolio/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codes }),
  });
  const data = await resp.json();

  const portfolio = await fetchPortfolio();
  initPortfolioFromPositions(portfolio.positions);
  document.getElementById('msg').innerText = data.ok ? `同步完成：${data.count} 条` : '同步失败';
}

async function savePortfolio(){
  const rows = readPortfolio();
  for (const row of rows) {
    await fetch('/api/portfolio/positions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(row),
    });
  }
  document.getElementById('msg').innerText = `保存完成：${rows.length} 条`;
}

function switchMarket(market) {
  currentMarket = market;
  loadIndexes(market);
}

async function refreshMarketAndGold() {
  await Promise.all([loadIndexes(currentMarket), loadGoldQuotes()]);
}

async function loadIndexes(market) {
  const container = document.getElementById('indexCards');
  container.innerHTML = '加载中...';
  try {
    const resp = await fetch(`/api/indexes?market=${encodeURIComponent(market)}`);
    const data = await resp.json();
    container.innerHTML = '';
    (data.quotes || []).forEach(q => {
      const cls = Number(q.change_percent) >= 0 ? 'up' : 'down';
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `<div><b>${q.name}</b> (${q.code})</div>
        <div>${Number(q.current).toFixed(2)}</div>
        <div class='${cls}'>${Number(q.change_value).toFixed(2)} (${Number(q.change_percent).toFixed(2)}%)</div>
        <div class='muted'>${q.market.toUpperCase()} / ${q.status}</div>`;
      container.appendChild(card);
    });
  } catch (_) {
    container.innerHTML = '指数加载失败';
  }
}

async function loadGoldQuotes() {
  const container = document.getElementById('goldCards');
  container.innerHTML = '加载中...';
  try {
    const resp = await fetch('/api/gold/realtime');
    const data = await resp.json();
    container.innerHTML = '';
    (data.quotes || []).forEach(q => {
      const cls = Number(q.change_percent) >= 0 ? 'up' : 'down';
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `<div><b>${q.platform}</b></div>
        <div>${Number(q.price).toFixed(2)} 元/克</div>
        <div class='${cls}'>${Number(q.change).toFixed(2)} (${Number(q.change_percent).toFixed(2)}%)</div>
        <div class='muted'>${q.status}</div>`;
      container.appendChild(card);
    });
  } catch (_) {
    container.innerHTML = '黄金报价加载失败';
  }
}

async function runEstimate(){
  const codes=document.getElementById('codes').value.split(/[\s,，]+/).filter(Boolean);
  const portfolioResp = await fetchPortfolio();
  const portfolioMap = {};
  portfolioResp.positions.forEach(p => { portfolioMap[p.code] = p; });

  document.getElementById('msg').innerText='抓取中，请稍候...';
  const resp=await fetch('/api/estimate?codes='+encodeURIComponent(codes.join(',')));
  const data=await resp.json();

  document.getElementById('msg').innerText=data.failures.length
    ? ('部分失败: '+data.failures.join(' | '))
    : '抓取完成';

  const summaryDiv=document.getElementById('summary');
  summaryDiv.innerHTML='';
  let html='<table><tr><th>基金代码</th><th>基金名称</th><th>披露期</th><th>持仓源</th><th>预估涨跌(%)</th><th>行情覆盖权重(%)</th><th>当前持有收益(元)</th><th>预估当日盈亏(元)</th><th>操作</th></tr>';
  data.results.forEach(r=>{
    const p=portfolioMap[r.code] || {share:0,cost:0,current_profit:0};
    const estimatePnL = Number(p.share || 0) * Number(p.cost || 0) * (r.estimated_pct/100);
    html += `<tr><td>${r.code}</td><td>${r.name}</td><td>${r.report_period}</td><td>${r.source}</td>
      <td>${r.estimated_pct.toFixed(3)}</td><td>${r.matched_weight.toFixed(2)}</td>
      <td>${Number(p.current_profit || 0).toFixed(2)}</td><td>${estimatePnL.toFixed(2)}</td>
      <td><button onclick="openFundDetail('${r.code}')">详情</button></td></tr>`;
  });
  html+='</table>';
  summaryDiv.innerHTML=html;

  const detailDiv=document.getElementById('details');
  detailDiv.innerHTML='';
  data.results.forEach(r=>{
    let inner='';
    if(r.missing_symbols.length){
      inner += `<p>以下成分未匹配行情，按 0% 处理：${r.missing_symbols.join(', ')}</p>`;
    }
    inner += '<table><tr><th>代码</th><th>名称</th><th>权重(%)</th><th>实时涨跌(%)</th><th>贡献(%)</th></tr>';
    r.details.forEach(x=>{
      inner += `<tr><td>${x.symbol}</td><td>${x.name}</td><td>${x.weight}</td><td>${x.change}</td><td>${x.contribution}</td></tr>`;
    });
    inner += '</table>';

    const d=document.createElement('details');
    d.innerHTML=`<summary>${r.name}（${r.code}）| 预估 ${r.estimated_pct.toFixed(3)}% | 披露期: ${r.report_period} | 源: ${r.source}</summary>${inner}`;
    detailDiv.appendChild(d);
  });
}

function switchDetailTab(tab) {
  ['history', 'stage', 'nav', 'holding'].forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    if (el) el.classList.toggle('active', t === tab);
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

  document.getElementById('detailTitle').innerText = `${data.name}（${data.code}）`;
  document.getElementById('detailMeta').innerText = `预估 ${Number(data.estimated_pct).toFixed(3)}% | 覆盖权重 ${Number(data.matched_weight).toFixed(2)}% | ${data.report_period} | ${data.source}`;

  document.getElementById('tab-history').innerHTML = `
    <p>基金代码：${data.code}</p>
    <p>基金名称：${data.name}</p>
    <p>当前预估涨跌：${Number(data.estimated_pct).toFixed(3)}%</p>
  `;

  let stageHtml = '<table><tr><th>区间</th><th>基金收益(%)</th><th>同类均值(%)</th><th>业绩基准(%)</th><th>排名</th></tr>';
  (data.stage_performance || []).forEach(s => {
    stageHtml += `<tr><td>${s.period}</td><td>${s.fund_return}</td><td>${s.category_avg}</td><td>${s.benchmark}</td><td>${s.rank}</td></tr>`;
  });
  stageHtml += '</table>';
  document.getElementById('tab-stage').innerHTML = stageHtml;

  let holdingHtml = '<table><tr><th>代码</th><th>名称</th><th>权重(%)</th><th>实时涨跌(%)</th><th>贡献(%)</th></tr>';
  (data.holdings || []).forEach(h => {
    holdingHtml += `<tr><td>${h.symbol}</td><td>${h.name}</td><td>${h.weight}</td><td>${h.change}</td><td>${h.contribution}</td></tr>`;
  });
  holdingHtml += '</table>';
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
  const pad = 30;

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#ddd';
  ctx.strokeRect(0, 0, w, h);

  const values = rows.map(r => Number(r.nav));
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const span = Math.max(0.0001, maxV - minV);

  ctx.beginPath();
  ctx.strokeStyle = '#1a73e8';
  ctx.lineWidth = 2;
  rows.forEach((r, i) => {
    const x = pad + (w - pad * 2) * (i / (rows.length - 1 || 1));
    const y = h - pad - ((Number(r.nav) - minV) / span) * (h - pad * 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  const legend = document.getElementById('navLegend');
  legend.innerText = `区间: ${rows[0].date} ~ ${rows[rows.length - 1].date} | 最低 ${minV.toFixed(4)} | 最高 ${maxV.toFixed(4)}`;
}

bootstrap();
