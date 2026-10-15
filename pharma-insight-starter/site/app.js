/* No framework needed. All external API data is inserted as plain text, not HTML. */
const state = { records: [], view: "all", query: "", phase: "all", status: "all", demo: false };
const byId = (id) => document.getElementById(id);
const safe = (value) => String(value ?? "").trim();
const fmtDate = (str) => /^\d{4}-\d{2}-\d{2}$/.test(safe(str)) ? str : "날짜 미확인";
function el(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== undefined) element.textContent = value;
  return element;
}
function setNotice(message, type) {
  const notice = byId("notice"); notice.textContent = message;
  notice.className = "notice " + type;
}
function visibleRecords() {
  return state.records.filter((r) => {
    if (state.view !== "all" && r.type !== state.view) return false;
    if (r.type === "trial" && state.phase !== "all" && !((r.phases || []).includes(state.phase))) return false;
    if (r.type === "trial" && state.status !== "all" && r.status !== state.status) return false;
    const combined = [r.title, r.company, r.condition, r.drug, r.id, r.application_number, r.status, ...(r.phases || [])].map(safe).join(" ").toLocaleLowerCase();
    return combined.includes(state.query.toLocaleLowerCase());
  }).sort((a, b) => safe(b.date).localeCompare(safe(a.date)));
}
function makeCard(record) {
  const card = el("article", "item");
  const top = el("div", "item-top");
  top.append(el("span", "tag " + (record.type === "fda" ? "fda" : "trial"), record.type === "fda" ? "FDA · 원승인" : "CLINICAL TRIAL"));
  top.append(el("span", "item-date", fmtDate(record.date)));
  card.append(top);
  card.append(el("h3", "", safe(record.title) || "제목 없음"));
  const description = record.type === "fda"
    ? `신청회사: ${safe(record.company) || "정보 없음"}`
    : `기관/회사: ${safe(record.company) || "정보 없음"} · 질환: ${safe(record.condition) || "정보 없음"}`;
  card.append(el("p", "item-desc", description));
  const chips = el("div", "chips");
  let labels = record.type === "fda" ? [safe(record.drug), "NDA/BLA original"] : [safe(record.drug), ...(record.phases || []).map(p => p.replace("PHASE", "Phase ")), safe(record.status).replaceAll("_", " ")];
  labels.filter(Boolean).slice(0, 4).forEach((label) => chips.append(el("span", "chip", label.length > 45 ? label.slice(0, 45) + "…" : label)));
  card.append(chips);
  const bottom = el("div", "item-bottom");
  bottom.append(el("span", "item-identifier", safe(record.id)));
  const a = el("a", "source-link", "공식 원문 보기 ↗");
  try {
    const url = new URL(safe(record.url));
    if (url.protocol === "https:" && ["clinicaltrials.gov", "www.accessdata.fda.gov", "open.fda.gov"].includes(url.hostname)) {
      a.href = url.href; a.target = "_blank"; a.rel = "noopener noreferrer";
    } else { a.textContent = "출처 링크 없음"; a.removeAttribute("href"); }
  } catch { a.textContent = "출처 링크 없음"; }
  bottom.append(a); card.append(bottom); return card;
}
function render() {
  const filtered = visibleRecords();
  const cards = byId("cards"); cards.replaceChildren(...filtered.map(makeCard));
  byId("result-count").textContent = `${filtered.length}건 표시`;
  byId("empty").hidden = filtered.length > 0;
  byId("phase").disabled = state.view === "fda";
  byId("status").disabled = state.view === "fda";
}
async function init() {
  try {
    const response = await fetch("./data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.records = [...(payload.fda || []), ...(payload.trials || [])];
    state.demo = payload.mode === "demo";
    byId("metric-all").textContent = state.records.length.toLocaleString("ko-KR");
    byId("metric-fda").textContent = (payload.fda || []).length.toLocaleString("ko-KR");
    byId("metric-trial").textContent = (payload.trials || []).length.toLocaleString("ko-KR");
    if (payload.updated_at && !state.demo) {
      const ts = new Date(payload.updated_at);
      byId("updated-at").textContent = "마지막 데이터 수집: " + ts.toLocaleString("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "short" }) + " (한국시간)";
    } else { byId("updated-at").textContent = "사이트 미리보기 · 예시 자료"; }
    if (state.demo) setNotice("미리보기용 가상 데이터입니다. GitHub Actions를 실행하면 공식 API에서 수집한 실제 기록으로 대체됩니다.", "demo");
    else if ((payload.errors || []).length) setNotice("일부 데이터 소스의 수집에 실패했습니다. " + payload.errors.join(" / "), "warning");
    else setNotice("공식 API 수집 완료. 숫자는 전체 DB 통계가 아니라 이 사이트에 표시하는 기록 수입니다.", "success");
    render();
  } catch (error) {
    setNotice("data.json 파일을 불러오지 못했습니다. 브라우저에서 직접 HTML 파일을 여는 대신 로컬 서버 또는 GitHub Pages로 확인하세요.", "warning");
    byId("metric-all").textContent = "0"; byId("metric-fda").textContent = "0"; byId("metric-trial").textContent = "0";
    render(); console.error(error);
  }
}
document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => {
  state.view = button.dataset.view;
  document.querySelectorAll(".tab").forEach(b => { b.classList.toggle("selected", b === button); b.setAttribute("aria-pressed", String(b === button)); });
  render();
}));
byId("query").addEventListener("input", e => { state.query = e.target.value.trim(); render(); });
byId("phase").addEventListener("change", e => { state.phase = e.target.value; render(); });
byId("status").addEventListener("change", e => { state.status = e.target.value; render(); });
init();
