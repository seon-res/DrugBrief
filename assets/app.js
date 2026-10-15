/* DrugBrief dashboard — static application, no API credentials in browser. */
'use strict';
const TAB_INFO = {
  approvals:{name:'신규 의약품 허가·FDA 승인',short:'의약품 허가·승인',sub:'NDA / BLA 원허가',icon:'✦',headline:'새롭게 허가된 의약품을 한눈에',desc:'FDA Drugs@FDA 원허가 기록과 승인 내용 요약을 제공합니다. 승인서 확인 완료·자동 발췌·확인 필요를 구분합니다.'},
  trials:{name:'임상시험 진행 현황',short:'임상시험 현황',sub:'Phase 1 · 2 · 3 · 4',icon:'◈',headline:'글로벌 임상시험 진행 상황 확인',desc:'ClinicalTrials.gov에 등록된 의약품 및 생물학적 제제 중재시험 중 최근 변경된 정보를 제공합니다.'},
  regulations:{name:'제약 규제·가이드라인 변경',short:'규제·가이드라인',sub:'FDA · EMA · 식약처',icon:'▤',headline:'규제와 가이드라인의 변화를 놓치지 마세요',desc:'공식 규제 자료와 업로드된 기존 규제정보 아카이브를 통합해 검색할 수 있습니다.'}
};
const STATUS_KR={RECRUITING:'모집 중',NOT_YET_RECRUITING:'모집 예정',ACTIVE_NOT_RECRUITING:'진행 중·모집 종료',COMPLETED:'완료',TERMINATED:'중단',WITHDRAWN:'철회',SUSPENDED:'일시 중단',ENROLLING_BY_INVITATION:'초청 모집',UNKNOWN:'상태 미상'};
const $ = q => document.querySelector(q);
const state={tab:new URLSearchParams(location.search).get('tab')||'approvals',search:'',agency:'all',stage:'all',sort:'new',page:1,pageSize:15,historyData:null,regulationsCombined:null,historyLoading:false,historyError:'',data:{approvals:[],trials:[],regulations:[]},meta:{},selected:null};
if(!TAB_INFO[state.tab])state.tab='approvals';
const esc = s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = s=>{try{const u=new URL(String(s||''));return u.protocol==='https:'||u.protocol==='http:'?u.href:''}catch{return ''}};
const prettyDate = v=>/^\d{4}-\d{2}-\d{2}$/.test(String(v||''))?v:'날짜 미기재';
const num = n=>Number(n||0).toLocaleString('ko-KR');
const keys = {fda:'FDA',trials:'임상시험',federal_register:'연방관보',ema:'EMA'};

async function dataLoad(path){
  const res=await fetch(`./data/${path}`,{cache:'no-cache'});
  if(!res.ok)throw Error(`${path}: HTTP ${res.status}`);
  return res.json();
}
function records(){
  if(state.tab==='regulations')return state.regulationsCombined||state.data.regulations||[];
  return state.data[state.tab]||[];
}
function combineAllRegulations(){
  const dict=new Map((state.historyData||[]).map(x=>[x.id,x]));
  for(const x of (state.data.regulations||[]))dict.set(x.id,x);
  state.regulationsCombined=[...dict.values()].sort((a,b)=>(b.date||'').localeCompare(a.date||''));
}
async function ensureRegulationHistory(){
  if(state.historyData||state.historyLoading)return;
  state.historyLoading=true;
  if(state.tab==='regulations')render();
  try{
    const items=await dataLoad('regulations-history.json');
    if(!Array.isArray(items))throw Error('전체 아카이브 데이터 형식이 올바르지 않습니다.');
    state.historyData=items;
    combineAllRegulations();
    state.historyError='';
  }catch(e){
    state.historyError=e.message||String(e);
  }finally{
    state.historyLoading=false;
    state.page=1;
    if(state.tab==='regulations')render();
  }
}
function kindStatus(){
  if(state.tab==='approvals')return state.meta.sources?.fda;
  if(state.tab==='trials')return state.meta.sources?.trials;
  return null;
}
function statCards(){
  const data=records();
  const table=state.tab;
  if(table==='approvals'){
    const nda=data.filter(x=>x.approval_type?.includes('NDA')).length;
    const bla=data.filter(x=>x.approval_type?.includes('BLA')).length;
    const reviewed=data.filter(x=>x.reason_status==='verified').length;
    return [['기록된 원허가',num(data.length),'현재 수집 목록'],['NDA 원허가',num(nda),'신규 의약품 신청'],['BLA 원허가',num(bla),'바이오의약품 신청'],['승인서 검토 완료',num(reviewed),'원문 근거 확인·한국어 요약']];
  }
  if(table==='trials'){
    const active=data.filter(x=>['RECRUITING','NOT_YET_RECRUITING'].includes(x.status)).length;
    const phase3=data.filter(x=>(x.phase||'').includes('Phase 3')).length;
    return [['조회된 임상시험',num(data.length),'최근 업데이트 샘플'],['모집 중·예정',num(active),'등록된 모집 상태'],['Phase 3',num(phase3),'3상 포함 연구'],['최근 변경 등록일',data[0]?.date||'—','승인일이 아닌 변경 게시일']];
  }
  return [['규제 관련 기록',num(data.length),state.historyData?'2015년 이후 전체 아카이브 + 최신 자료':'전체 아카이브 자동 로드 중'],['FDA 관련',num(data.filter(x=>x.agency?.includes('FDA')).length),'FDA / 연방관보'],['EMA 관련',num(data.filter(x=>x.agency==='EMA').length),'유럽 규제 자료'],['식약처 관련',num(data.filter(x=>x.agency==='식약처').length),'원본 ZIP 과거 기록']];
}
function filterOptions(){
  const rows=records();
  const companies=[...new Set(rows.map(x=>x.agency).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'ko'));
  const agencies=['<option value="all">전체 기관</option>',...companies.map(a=>`<option value="${esc(a)}" ${state.agency===a?'selected':''}>${esc(a)}</option>`)];
  const choices=state.tab==='approvals'?[['NDA','NDA 원허가'],['BLA','BLA 원허가']]:state.tab==='trials'?[['Phase 1','Phase 1'],['Phase 2','Phase 2'],['Phase 3','Phase 3'],['Phase 4','Phase 4'],['RECRUITING','모집 중'],['NOT_YET_RECRUITING','모집 예정'],['COMPLETED','완료']]:[['가이드라인','가이드라인'],['법령','법령·규칙'],['식약처','식약처 관련'],['FDA','FDA 관련'],['EMA','EMA 관련']];
  const special=['<option value="all">'+(state.tab==='trials'?'전체 Phase/상태':'전체 세부 유형')+'</option>',...choices.map(([v,t])=>`<option ${v===state.stage?'selected':''} value="${esc(v)}">${esc(t)}</option>`)];
  return {agencies:agencies.join(''),stage:special.join('')};
}
function filtered(){
  const q=state.search.toLocaleLowerCase().trim();
  let rows=records().filter(x=>{
    if(state.agency!=='all'&&x.agency!==state.agency)return false;
    if(state.stage!=='all'){
      if(state.tab==='approvals'&&!(x.approval_type||'').includes(state.stage))return false;
      if(state.tab==='trials'&&!(x.phase||'').includes(state.stage)&&x.status!==state.stage)return false;
      if(state.tab==='regulations'&&!([x.reg_type,x.agency,x.title,x.description].join(' ').toLowerCase().includes(state.stage.toLowerCase())))return false;
    }
    if(!q)return true;
    return [x.title,x.subtitle,x.company,x.application,x.id,x.phase,x.status,x.reg_type,x.agency,x.description,x.approval_reason,x.reason_category,x.interventions?.join(' ')].some(s=>String(s||'').toLocaleLowerCase().includes(q));
  });
  rows.sort((a,b)=>state.sort==='old'?(a.date||'').localeCompare(b.date||''):(b.date||'').localeCompare(a.date||''));
  return rows;
}
function chip(text,cls=''){return `<span class="pill ${cls}">${esc(text)}</span>`}
function groupChip(item){
  if(state.tab==='approvals')return chip(item.approval_type||'FDA 원허가');
  if(state.tab==='trials')return chip(item.phase||'Phase 미기재');
  return chip(item.agency||'규제 기관');
}
function statusChip(item){
  if(state.tab==='approvals')return chip('승인','green');
  if(state.tab==='trials'){
    const s=STATUS_KR[item.status]||item.status||'상태 확인';
    const cl=['RECRUITING','NOT_YET_RECRUITING'].includes(item.status)?'green':'gray';
    return chip(s,cl);
  }
  return chip(item.is_historical?'과거 스냅샷':item.reg_type||'공식 자료',item.is_historical?'gray':'green');
}
function approvalReasonHtml(item){
  if(state.tab!=='approvals')return '';
  const verified=item.reason_status==='verified';
  const automatic=item.reason_status==='auto_extracted';
  const basis=verified?'FDA 승인서 확인 완료':automatic?'FDA 승인서 영문 자동 발췌 · 검토 필요':'승인서 내용 미확인';
  const reason=item.approval_reason||'승인 내용을 확인 중입니다. FDA 원문을 확인하세요.';
  const link=safeUrl(item.reason_source_url||item.approval_letter_url||item.url);
  return `<div class="approval-reason ${verified?'verified':''}"><div class="approval-reason-head"><strong>이번 NDA/BLA의 승인 내용</strong><span class="approval-basis">${esc(basis)}</span></div><p>${esc(reason)}</p>${link?`<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${verified||automatic?'FDA 승인서 확인 ↗':'FDA 공식 원문 보기 ↗'}</a>`:''}</div>`;
}
function card(item, idx){
  const desc=item.subtitle||item.description||'';
  const meta=state.tab==='approvals'?[item.company,item.application,prettyDate(item.date)]:state.tab==='trials'?[item.id,item.company,prettyDate(item.date)]:[item.reg_type,item.agency,prettyDate(item.date)];
  return `<article class="record">
      <div class="record-number">${String(idx+1).padStart(2,'0')}</div>
      <div><div class="record-top">${groupChip(item)}${statusChip(item)}</div>
      <button class="record-title" data-detail="${esc(item.id)}" type="button">${esc(item.title||'제목 없음')}</button>
      <p class="record-desc">${esc(desc)}</p>${approvalReasonHtml(item)}
      <div class="record-meta">${meta.filter(Boolean).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>
    </article>`;
}
function rowHtml(rows){
  const begin=(state.page-1)*state.pageSize;
  return rows.slice(begin,begin+state.pageSize).map((x,i)=>card(x,begin+i)).join('')||`<div class="empty"><strong>검색 결과가 없습니다.</strong>검색어나 필터를 바꿔보세요. API 데이터가 아직 없다면 GitHub Actions 수집을 실행하세요.</div>`;
}
function pageHtml(rows){
  const max=Math.max(1,Math.ceil(rows.length/state.pageSize));
  if(state.page>max)state.page=max;
  return `<div class="pagination"><button id="prev-page" ${state.page<=1?'disabled':''}>← 이전</button><span>${num(state.page)} / ${num(max)} 페이지</span><button id="next-page" ${state.page>=max?'disabled':''}>다음 →</button></div>`;
}
function sourceStatuses(){
  const map=state.meta.sources||{};
  return Object.entries(keys).map(([key,label])=>{
    const s=map[key]||{state:'pending'};
    const status=s.state==='ok'?'수집 성공':s.state==='stale'?'지난 자료 유지':s.state==='error'?'수집 실패':'첫 수집 대기';
    return `<span class="source-status ${esc(s.state)}" title="${esc(s.message||'')}"><span class="mini-dot"></span>${label} · ${status}</span>`;
  }).join('');
}
function statsBars(){
  const arr=records(); let counts={};
  for(const rec of arr){
    const label=state.tab==='approvals'?(rec.approval_type||'기타'):state.tab==='trials'?(rec.phase||'해당 없음'):rec.agency||'기타';
    counts[label]=(counts[label]||0)+1;
  }
  const pairs=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5);
  const max=pairs[0]?.[1]||1;
  return pairs.map(([name,count])=>`<div><div class="bar-top"><span title="${esc(name)}">${esc(name)}</span><b>${num(count)}</b></div><div class="bar-track"><span style="width:${Math.max(3,100*count/max)}%"></span></div></div>`).join('')||'<p>수집 후 통계가 표시됩니다.</p>';
}
function extraNotice(){
  const s=kindStatus();
  if(s?.state==='pending'||s?.state==='error')return `<div class="alert warning">⚠️ <div><strong>${state.tab==='approvals'?'FDA':'임상시험'} 데이터가 아직 준비되지 않았습니다.</strong><br>GitHub 저장소의 Actions → DrugBrief 데이터 수집 및 배포 → Run workflow를 실행하세요. 다른 탭의 원본 규제 자료는 현재 열람할 수 있습니다.</div></div>`;
  if(s?.state==='stale')return `<div class="alert warning">⚠️ <div>최근 수집이 실패하여 <strong>마지막으로 저장된 자료</strong>를 보여주고 있습니다. 출처 상태와 날짜를 확인하세요.</div></div>`;
  if(state.tab==='regulations' && state.historyError)return `<div class="alert warning">⚠️ <div>전체 규제 아카이브를 읽지 못했습니다. 최신 규제 기록만 표시 중입니다. (${esc(state.historyError)})</div></div>`;
  if(state.tab==='regulations' && state.historyLoading)return `<div class="alert"><span class="spinner"></span><div>2015년부터의 규제 아카이브를 자동으로 불러오는 중입니다. 완료되면 체크 없이 전체 기록을 검색할 수 있습니다.</div></div>`;
  if(state.tab==='regulations')return `<div class="alert">ⓘ <div>규제 아카이브의 기존 자료는 <strong>2026-10-15 원본 ZIP 스냅샷</strong>입니다. 이후 Federal Register 및 EMA 갱신 자료가 합쳐집니다. 과거 기록은 원문으로 재확인하세요.</div></div>`;
  if(state.tab==='trials')return `<div class="alert">ⓘ <div><strong>최근 변경된 임상시험 표본</strong>을 보여줍니다. 전 세계 모든 임상시험의 전체 목록이나 신규 개시 건수를 의미하지 않습니다.</div></div>`;
  const coverage=state.meta.fda_coverage||{};
  const coverageLabel=coverage.history_complete?'2015년 1월 1일부터 FDA 원허가 기록을 조회해 누적한 목록입니다.':'2015년부터 과거 FDA 원허가 기록을 수집하도록 업데이트되었습니다. 첫 배포 후 과거 자료 수집이 완료되어야 전체 기간이 표시됩니다.';
  return `<div class="alert">ⓘ <div>${coverageLabel} 모든 NDA/BLA 원허가가 혁신 신약(NME)이나 신규 적응증 승인인 것은 아닙니다. 원본 API의 제공 범위·갱신 시점에 따라 누락될 수 있습니다.</div></div>`;
}
function aside(){
  const sourceLinks=state.tab==='approvals'?[['openFDA Drugs@FDA','https://open.fda.gov/apis/drug/drugsfda/'],['FDA Novel Drug Approvals','https://www.fda.gov/drugs/development-approval-process-drugs/novel-drug-approvals-fda']]:state.tab==='trials'?[['ClinicalTrials.gov','https://clinicaltrials.gov/'],['공식 API 문서','https://clinicaltrials.gov/data-api/api']]:[['FDA Federal Register','https://www.federalregister.gov/agencies/food-and-drug-administration'],['EMA RSS','https://www.ema.europa.eu/en/news-events/rss-feeds'],['식약처','https://www.mfds.go.kr/']];
  const tips=state.tab==='approvals'?["FDA 신청번호(NDA/BLA)로 구분합니다.","원허가 기준으로 분류하며 제네릭 ANDA는 제외합니다.","확인 완료 표시는 FDA 원허가 승인서에 근거한 한국어 요약에만 사용합니다.","자동 발췌된 영문과 제출 분류는 완전한 승인 사유가 아니므로 원문을 검토하세요."]:state.tab==='trials'?["모집 상태와 Phase는 등록자가 제출한 정보입니다.","업데이트 날짜는 임상시험 개시일과 다릅니다.","연구 등록은 FDA 승인 또는 임상적 유효성을 보장하지 않습니다."]:["기존 ZIP의 규제 자료를 보존합니다.","연방관보는 규제안·고시·최종규칙 등을 포함합니다.","효력 발생일은 게시일과 다를 수 있으므로 원문에서 확인하세요."];
  return `<aside class="aside">
    <section class="panel aside-block"><h3>데이터 구성</h3><p>현재 선택한 메뉴의 수집 자료를 기준으로 분포를 표시합니다.</p><div class="bars">${statsBars()}</div></section>
    <section class="panel aside-block"><h3>공식 데이터 출처</h3><p>주요 원본을 직접 확인할 수 있습니다.</p><div class="source-list">${sourceLinks.map(([label,url])=>`<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} <span>↗</span></a>`).join('')}</div></section>
    <section class="panel aside-block"><h3>해석 시 주의사항</h3><ul class="guide-list">${tips.map(t=>`<li>${esc(t)}</li>`).join('')}</ul></section>
    <section class="panel aside-block"><h3>데이터 수집 기준</h3><p>갱신 시각<br><strong>${esc(state.meta.updated_at||'첫 자동 수집 전')}</strong></p><p>규제 스냅샷: 2026-10-15</p><a class="source-link" href="./README.md" target="_blank">수집 방식·한계 보기 <span>↗</span></a></section>
  </aside>`;
}
function layout(){
  const tab=TAB_INFO[state.tab], rows=filtered();
  const s=filterOptions();
  const stats=statCards();
  const updated=state.meta.updated_at ? state.meta.updated_at.replace('T',' ').slice(0,16)+' KST' : '자동 수집 실행 전';
  return `<header class="site-header"><div class="container header-inner">
     <a href="./" class="brand"><span class="eyebrow">PHARMA & CLINICAL INTELLIGENCE</span><strong>DrugBrief<span style="color:#0aa2a6">.</span></strong><small>의약품 허가 · 임상시험 · 규제동향 통합 대시보드</small></a>
     <div class="top-links"><div class="header-status"><span class="live-dot ${Object.values(state.meta.sources||{}).some(x=>x.state==='ok')?'good':''}"></span><span>${esc(updated)}</span></div><a href="https://github.com" target="_blank" rel="noopener noreferrer">GitHub ↗</a></div>
   </div></header>
   <main class="container"><section class="hero"><div><div class="hero-label">DRUG DEVELOPMENT WATCH</div><h1>${esc(tab.headline)}</h1><p>${esc(tab.desc)}</p></div><div class="hero-mark"><b>03</b><span>INTELLIGENCE AREAS</span></div></section>
   <nav class="tabs" aria-label="사이트 주요 메뉴">${Object.entries(TAB_INFO).map(([id,t])=>`<button class="tab ${state.tab===id?'active':''}" aria-pressed="${state.tab===id}" data-tab="${id}"><span class="tab-icon">${t.icon}</span><span><b>${esc(t.short)}</b><small>${esc(t.sub)}</small></span></button>`).join('')}</nav>
   <div class="section-heading"><div><span class="section-kicker">${esc(state.tab.toUpperCase())} OVERVIEW</span><h2>${esc(tab.name)}</h2><p>공식 기록을 기준으로 검색·비교하고 상세 원문을 확인하세요.</p></div></div>
   <div class="stats">${stats.map(([label,value,desc])=>`<div class="stat"><span class="stat-label">${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(desc)}</small></div>`).join('')}</div>
   ${extraNotice()}<div class="status-tags">${sourceStatuses()}</div>
   <div class="content-grid"><section class="panel"><div class="panel-header"><div class="panel-title">${esc(tab.name)} 목록</div><div class="panel-sub">기업명·의약품명·기관명·번호로 검색할 수 있습니다.</div>
   ${state.tab==='regulations'?`<div class="archive-switch"><div style="font-size:11px;color:#385a72"><strong>${state.historyData?'✓ 전체 규제 아카이브 검색 활성화':state.historyLoading?'전체 규제 아카이브 불러오는 중…':'전체 규제 아카이브 자동 검색'}</strong><br>${state.historyData?'2015년부터의 과거 기록 및 최신 자료를 체크 없이 모두 검색합니다.':state.historyError?'아카이브 로드에 실패하여 최신 목록만 표시합니다.':'과거 약 '+num(state.meta.historic_total||6944)+'건을 자동 로드합니다.'}</div></div>`:''}
   </div>
   <div class="filters"><label class="search"><span class="search-icon">⌕</span><input id="search" autocomplete="off" aria-label="통합 검색" placeholder="의약품·질환·기업·NCT 번호 또는 규제 키워드 검색" value="${esc(state.search)}"></label>
   <div class="filter-row"><select id="agency" aria-label="기관 선택">${s.agencies}</select><select id="stage" aria-label="세부 유형">${s.stage}</select><select id="sort" aria-label="정렬"><option value="new" ${state.sort==='new'?'selected':''}>최신순</option><option value="old" ${state.sort==='old'?'selected':''}>오래된 순</option></select></div></div>
   <div class="filter-summary"><span>검색 결과 <strong>${num(rows.length)}건</strong>${state.search?' · 검색어: '+esc(state.search):''}</span><span class="action-buttons"><button class="text-button" id="clear-filters">필터 초기화</button><button class="text-button" id="export-csv">CSV 다운로드 ↧</button></span></div>
   <div class="records">${rowHtml(rows)}</div>${pageHtml(rows)}</section>${aside()}</div>
   <footer class="page-footer"><div>DrugBrief · 공식 공공데이터 기반 학습·리서치용 정보 서비스<br>의약품 허가, 임상시험 상태 및 법규 변경 여부는 반드시 최신 공식 원문을 확인하세요.</div><div>규제 과거 데이터: 사용자 제공 <a href="https://github.com/nawoonkim423/pharma-regulation-site" target="_blank" rel="noopener noreferrer">pharma-regulation-site</a> 원본에서 재구성</div></footer>
   </main><div id="modal-root"></div>`;
}
function changeTab(tab){if(!TAB_INFO[tab])return;state.tab=tab;state.search='';state.stage='all';state.agency='all';state.page=1;state.sort='new';const p=new URLSearchParams(location.search);p.set('tab',tab);history.replaceState(null,'',location.pathname+'?'+p.toString());render();if(tab==='regulations')ensureRegulationHistory();}
function openModal(id){
  const item=records().find(x=>x.id===id);if(!item)return;
  state.selected=id;
  const fields=[['자료 번호',item.id],['발표·기록 기관',item.agency],['기관/개발사',item.company],['원문 기준일',prettyDate(item.date)],['날짜 기준',item.date_basis],['자료 유형',item.approval_type||item.phase||item.reg_type],['진행 상태',STATUS_KR[item.status]||item.status],['FDA 신청번호',item.application],['제출 분류',item.classification],['제품 제형',item.dosage_form],['승인 근거 상태',item.reason_basis],['승인 사유 확인일',item.reason_verified_at],['임상시험 최초 게시일',item.first_posted],['등록된 중재물질',item.interventions?.join(' / ')],['목표·예상 등록인원',item.enrollment],['원본 스냅샷 기준일',item.archive_snapshot],['원본 데이터 출처',item.source]];
  const url=safeUrl(item.url);
  const root=$('#modal-root');
  root.innerHTML=`<div class="modal-overlay" id="modal-backdrop" role="presentation"><section class="detail-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><div>${groupChip(item)} ${statusChip(item)}</div><button class="close" id="close-modal" aria-label="닫기">×</button></div><h2 id="modal-title">${esc(item.title)}</h2><div class="detail-summary">${esc(item.description||item.subtitle||'원문에서 상세 내용을 확인하세요.')}</div>${approvalReasonHtml(item)}<dl class="detail-fields">${fields.filter(([,v])=>v!==null&&v!==undefined&&v!=='').map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" class="primary-link">Drugs@FDA 신청 정보 ↗</a>`:''}<p class="disclaimer">본 내용은 공개 자료의 탐색용 요약이며 법적·의료적 판단의 근거로 사용하지 마세요. 발표일, 시행일 및 최신 상태는 출처 원문을 확인해야 합니다.</p></section></div>`;
  document.body.style.overflow='hidden';
  $('#close-modal')?.focus();
  $('#close-modal')?.addEventListener('click',closeModal);
  $('#modal-backdrop')?.addEventListener('click',e=>{if(e.target.id==='modal-backdrop')closeModal();});
}
function closeModal(){const m=$('#modal-root');if(m)m.innerHTML='';state.selected=null;document.body.style.overflow='';}
function csvDownload(){
  const rows=filtered();
  const columns=['id','date','agency','title','company','status','phase','approval_type','application','reg_type','subtitle','approval_reason','reason_status','reason_source_url','url','source'];
  const sanitize=s=>{let t=String(s??'').replaceAll('\r',' ').replaceAll('\n',' ');if(/^[\s]*[=+@-]/.test(t))t="'"+t;return '"'+t.replaceAll('"','""')+'"'};
  const lines=[columns.join(','),...rows.map(r=>columns.map(c=>sanitize(Array.isArray(r[c])?r[c].join('; '):r[c])).join(','))];
  const file=new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(file);const a=document.createElement('a');a.href=url;a.download=`DrugBrief_${state.tab}_${new Date().toISOString().slice(0,10)}.csv`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
}

function render(focusSearch=false){
  const active=focusSearch ? [$('#search')?.selectionStart,$('#search')?.selectionEnd]:null;
  $('#app').innerHTML=layout();
  document.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>changeTab(btn.dataset.tab)));
  $('#search')?.addEventListener('input',e=>{state.search=e.target.value;state.page=1;render(true);});
  if(focusSearch){const x=$('#search');x?.focus();try{if(active&&active[0]!=null)x.setSelectionRange(active[0],active[1]);}catch{}}
  $('#agency')?.addEventListener('change',e=>{state.agency=e.target.value;state.page=1;render();});
  $('#stage')?.addEventListener('change',e=>{state.stage=e.target.value;state.page=1;render();});
  $('#sort')?.addEventListener('change',e=>{state.sort=e.target.value;state.page=1;render();});
  $('#clear-filters')?.addEventListener('click',()=>{state.search='';state.agency='all';state.stage='all';state.sort='new';state.page=1;render();});
  $('#export-csv')?.addEventListener('click',csvDownload);
  $('#prev-page')?.addEventListener('click',()=>{state.page--;render();$('.content-grid')?.scrollIntoView({behavior:'smooth'});});
  $('#next-page')?.addEventListener('click',()=>{state.page++;render();$('.content-grid')?.scrollIntoView({behavior:'smooth'});});
  document.querySelectorAll('[data-detail]').forEach(btn=>btn.addEventListener('click',()=>openModal(btn.dataset.detail)));
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
(async()=>{
  try{
    const [a,t,r,m]=await Promise.all([dataLoad('approvals.json'),dataLoad('trials.json'),dataLoad('regulations.json'),dataLoad('metadata.json')]);
    state.data={approvals:a,trials:t,regulations:r};state.meta=m;render();if(state.tab==='regulations')ensureRegulationHistory();
  }catch(e){
    $('#app').innerHTML=`<div class="container" style="padding-top:75px"><h1>데이터를 불러오지 못했습니다.</h1><p>${esc(e.message)}</p><p>파일을 직접 더블클릭해서 열었다면 브라우저에서 JSON을 차단할 수 있습니다. README의 로컬 서버 실행법을 참고하거나 GitHub Pages로 배포해 주세요.</p></div>`;
  }
})();
