const dateEl = document.getElementById("currentDate");
if (dateEl) {
  dateEl.textContent = new Date().toLocaleDateString("ar-EG", {
    weekday:"long", year:"numeric", month:"long", day:"numeric"
  });
}
setTimeout(() => {
  document.querySelectorAll(".flash-msg").forEach(el => {
    el.style.transition = "opacity .5s"; el.style.opacity = "0";
    setTimeout(() => el.remove(), 500);
  });
}, 4000);

function toggleSidebar() { document.querySelector(".sidebar").classList.toggle("open"); }

// يتحكم بإظهار/إخفاء قسم "نقاط الضعف" عند الطباعة فقط (لا يؤثر على العرض في الشاشة)
function toggleWeakPointsPrint(checkbox) {
  document.body.classList.toggle("hide-weak-points", !checkbox.checked);
}

const CAPACITY  = {
  "KG1":20,"KG2":20,"KG3":20,
  "أولى ابتدائي":24,"ثاني ابتدائي":24,"ثالث ابتدائي":24,
  "رابع ابتدائي":24,"خامس ابتدائي":24,"سادس ابتدائي":24,
  "أول متوسط":24,"ثاني متوسط":24,"ثالث متوسط":24,
  "أول ثانوي":30,"ثاني ثانوي":30,"ثالث ثانوي":30
};
const STANDARDS = { CCR:14, STR:50, SAR:90, SER:10 };

function recalcAll() {
  let tc=0, ts=0, tcp=0;
  document.querySelectorAll(".grade-classes").forEach(ci => {
    const keyBase = ci.name.replace("_classes","");
    const si  = document.querySelector(`input[name="${keyBase}_students"]`);
    const cap = parseInt(ci.dataset.capacity) || 24;
    const cl  = parseInt(ci.value)  || 0;
    const st  = parseInt(si?.value) || 0;
    const cp  = cl * cap; const vac = cp - st;
    const capEl = document.getElementById(`cap_${keyBase}`);
    const vacEl = document.getElementById(`vac_${keyBase}`);
    if (capEl) capEl.textContent = cp;
    if (vacEl) {
      if      (vac > 0) { vacEl.textContent = `شاغر: ${vac}`;           vacEl.className = "vacancy-badge vacancy-positive"; }
      else if (vac < 0) { vacEl.textContent = `زيادة: ${Math.abs(vac)}`;vacEl.className = "vacancy-badge vacancy-negative"; }
      else              { vacEl.textContent = "ممتلئ";                   vacEl.className = "vacancy-badge vacancy-zero"; }
    }
    tc += cl; ts += st; tcp += cp;
  });
  const tv = tcp - ts;
  const ad = tc > 0 ? (ts/tc).toFixed(1) : 0;
  const s = (id, v) => { const e=document.getElementById(id); if(e) e.textContent=v; };
  s("totalClassesDisplay",  tc);
  s("totalStudentsDisplay", ts.toLocaleString("ar"));
  s("totalCapacityDisplay", tcp.toLocaleString("ar"));
  s("totalVacanciesDisplay",tv);
  s("avgDensityDisplay",    ad);
  const teachers = parseInt(document.getElementById("input_teachers")?.value)      || 0;
  const admins   = parseInt(document.getElementById("input_admins")?.value)        || 0;
  const support  = parseInt(document.getElementById("input_support_staff")?.value) || 0;
  const total    = teachers + admins + support;
  const ratios   = {
    CCR: teachers>0 ? (ts/teachers).toFixed(2) : 0,
    STR: admins>0   ? (ts/admins  ).toFixed(2) : 0,
    SAR: support>0  ? (ts/support ).toFixed(2) : 0,
    SER: total>0    ? (ts/total   ).toFixed(2) : 0
  };
  Object.entries(ratios).forEach(([k,v]) => {
    const el = document.getElementById(`ratio_${k}`);
    if (!el) return;
    el.textContent = v;
    el.className   = `ratio-cell ${parseFloat(v) >= STANDARDS[k] ? "ratio-good" : "ratio-bad"}`;
  });
}
document.querySelectorAll(".grade-classes,.grade-students,.staff-input")
        .forEach(el => el.addEventListener("input", recalcAll));
if (document.querySelector(".grade-classes")) recalcAll();
