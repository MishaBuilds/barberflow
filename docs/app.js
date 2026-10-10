/* BarberFlow web-demo: честный демо-режим без сервера.
   Расписание генерируется детерминированно (то же правило, что и seed.py бота),
   записи живут только в localStorage этого браузера. */
(function () {
  "use strict";

  /* ---------- демо-данные (все выдуманы) ---------- */
  var SERVICES = [
    { id: 1, name: "Мужская стрижка", desc: "Консультация, мытьё, стрижка ножницами и машинкой, укладка.", price: 1200, dur: "60 мин" },
    { id: 2, name: "Стрижка + борода", desc: "Полный образ за один визит: стрижка и моделирование бороды.", price: 1700, dur: "90 мин" },
    { id: 3, name: "Оформление бороды", desc: "Контур, длина, уход маслом и укладка бороды.", price: 700, dur: "30 мин" },
    { id: 4, name: "Королевское бритьё", desc: "Горячее полотенце, опасная бритва, холодный компресс.", price: 1100, dur: "45 мин" },
    { id: 5, name: "Стрижка машинкой", desc: "Аккуратные переходы одной-двумя насадками, окантовка.", price: 900, dur: "30 мин" },
    { id: 6, name: "Укладка", desc: "Экспресс-укладка перед событием, подбор стайлинга.", price: 500, dur: "20 мин" }
  ];

  var MASTERS = [
    { id: 1, name: "Алексей", role: "Классика и фейд · 8 лет", about: "Спокойная рука, идеальные переходы. Любит короткие формы, которые месяц выглядят аккуратно.", tags: ["фейд", "классика", "седина"] },
    { id: 2, name: "Максим", role: "Борода и бритьё · 6 лет", about: "Контуры как по линейке, горячее бритьё без раздражения. Подберёт уход под вашу кожу.", tags: ["борода", "бритьё", "уход"] },
    { id: 3, name: "Кирилл", role: "Креатив и текстура · 5 лет", about: "Удлиненные формы, кропы, укладки с характером. Покажет, как повторить дома за 5 минут.", tags: ["кроп", "текстура", "укладка"] }
  ];

  var TIMES = ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30"];
  var DAYS = 7; // начиная с завтра, как в seed.py
  var WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  var MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  var LS_KEY = "bf_demo_bookings_v1";

  /* ---------- состояние ---------- */
  var state = { step: 1, serviceId: null, masterId: null, date: null, slot: null };
  var lastDone = null;

  /* ---------- утилиты ---------- */
  function $(id) { return document.getElementById(id); }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function isoOf(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function fmtDate(iso) {
    var p = iso.split("-");
    var d = new Date(+p[0], +p[1] - 1, +p[2]);
    return p[2] + "." + p[1] + " (" + WD[d.getDay()] + ")";
  }
  function fmtDateLong(iso) {
    var p = iso.split("-");
    var d = new Date(+p[0], +p[1] - 1, +p[2]);
    return p[2] + " " + MONTHS[d.getMonth()] + ", " + WD[d.getDay()];
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function loadBookings() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function saveBookings(arr) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(arr)); } catch (e) { /* приватный режим */ }
  }
  function isTaken(masterId, date, time) {
    return loadBookings().some(function (b) {
      return b.masterId === masterId && b.date === date && b.time === time;
    });
  }
  /* То же детерминированное правило занятости, что в database/seed.py:
     (mi + di + ti) % 3 == 0 → изначально занято. */
  function seedBusy(mi, di, ti) { return (mi + di + ti) % 3 === 0; }

  function dayList() {
    var out = [], now = new Date();
    for (var i = 1; i <= DAYS; i++) {
      var d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
      out.push({ iso: isoOf(d), di: i - 1 });
    }
    return out;
  }
  function serviceById(id) { return SERVICES.find(function (s) { return s.id === id; }) || null; }
  function masterById(id) { return MASTERS.find(function (m) { return m.id === id; }) || null; }

  /* Слоты мастера на дату с учётом seed-правила и демо-записей. */
  function slotsFor(masterId, di, dateIso) {
    var mi = masterId - 1;
    return TIMES.map(function (t, ti) {
      var busy = seedBusy(mi, di, ti) || isTaken(masterId, dateIso, t);
      return { time: t, busy: busy, masterId: masterId };
    });
  }
  /* Для «кто свободен раньше»: на каждое время — первый свободный мастер. */
  function slotsAny(di, dateIso) {
    return TIMES.map(function (t, ti) {
      var found = null;
      for (var m = 0; m < MASTERS.length; m++) {
        var mid = MASTERS[m].id;
        if (!seedBusy(m, di, ti) && !isTaken(mid, dateIso, t)) { found = mid; break; }
      }
      return { time: t, busy: found === null, masterId: found };
    });
  }

  /* ---------- тост ---------- */
  var toastTimer = null;
  function toast(msg) {
    var el = $("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, 3600);
  }

  /* ---------- рендер: услуги и мастера на странице ---------- */
  function renderCatalog() {
    $("services-list").innerHTML = SERVICES.map(function (s) {
      return '<li class="service-card">' +
        "<h3>" + esc(s.name) + "</h3>" +
        '<div class="service-meta"><span class="service-dur">' + esc(s.dur) + '</span>' +
        '<span class="service-price">' + s.price.toLocaleString("ru-RU") + " ₽</span></div>" +
        '<p class="service-desc">' + esc(s.desc) + "</p>" +
        '<p class="service-pick"><button class="btn btn-ghost btn-sm" type="button" data-pick-service="' + s.id + '">Выбрать</button></p>' +
        "</li>";
    }).join("");

    $("masters-grid").innerHTML = MASTERS.map(function (m) {
      var initials = m.name.slice(0, 1);
      return '<li class="master-card">' +
        '<div class="master-photo" aria-hidden="true">' + esc(initials) + "</div>" +
        "<h3>" + esc(m.name) + "</h3>" +
        '<p class="master-role">' + esc(m.role) + "</p>" +
        "<p>" + esc(m.about) + "</p>" +
        '<ul class="master-tags">' + m.tags.map(function (t) { return "<li>" + esc(t) + "</li>"; }).join("") + "</ul>" +
        '<p><button class="btn btn-ghost btn-sm" type="button" data-pick-master="' + m.id + '">Записаться к ' + esc(m.name) + "</button></p>" +
        "</li>";
    }).join("");
  }

  /* ---------- рендер: шаги ---------- */
  function renderServices() {
    $("choice-services").innerHTML = SERVICES.map(function (s) {
      var on = state.serviceId === s.id;
      return '<button class="choice" type="button" role="radio" aria-checked="' + on + '" data-service="' + s.id + '">' +
        '<span class="choice-radio" aria-hidden="true"></span>' +
        '<span class="choice-main"><strong>' + esc(s.name) + "</strong><small>" + esc(s.dur) + " · " + esc(s.desc) + "</small></span>" +
        '<span class="choice-price">' + s.price.toLocaleString("ru-RU") + " ₽</span></button>";
    }).join("");
  }

  function renderMasters() {
    var any = state.masterId === "any";
    var html = '<button class="choice" type="button" role="radio" aria-checked="' + any + '" data-master="any">' +
      '<span class="choice-radio" aria-hidden="true"></span>' +
      '<span class="choice-main"><strong>Кто свободен раньше</strong><small>Подберём ближайшее окно среди всех мастеров</small></span>' +
      '<span class="choice-price">—</span></button>';
    html += MASTERS.map(function (m) {
      var on = state.masterId === m.id;
      return '<button class="choice" type="button" role="radio" aria-checked="' + on + '" data-master="' + m.id + '">' +
        '<span class="choice-radio" aria-hidden="true"></span>' +
        '<span class="choice-main"><strong>' + esc(m.name) + "</strong><small>" + esc(m.role) + "</small></span>" +
        '<span class="choice-price">★ 4,9</span></button>';
    }).join("");
    $("choice-masters").innerHTML = html;
  }

  function renderDates() {
    var days = dayList();
    var useAny = state.masterId === "any";
    $("date-row").innerHTML = days.map(function (d) {
      var free;
      if (useAny) {
        free = slotsAny(d.di, d.iso).filter(function (s) { return !s.busy; }).length;
      } else {
        free = slotsFor(state.masterId, d.di, d.iso).filter(function (s) { return !s.busy; }).length;
      }
      var on = state.date === d.iso;
      return '<button class="date-chip" type="button" role="radio" aria-checked="' + on + '"' +
        ' data-date="' + d.iso + '"' + (free === 0 ? " disabled" : "") + ">" +
        fmtDate(d.iso) + "<small>" + (free === 0 ? "занято" : "свободно: " + free) + "</small></button>";
    }).join("");
  }

  function renderSlots() {
    var grid = $("slots-grid"), empty = $("slots-empty");
    if (!state.date) { grid.innerHTML = ""; empty.hidden = true; return; }
    var days = dayList();
    var di = days.find(function (d) { return d.iso === state.date; }).di;
    var slots = state.masterId === "any" ? slotsAny(di, state.date) : slotsFor(state.masterId, di, state.date);
    var freeCount = slots.filter(function (s) { return !s.busy; }).length;
    empty.hidden = freeCount !== 0;
    grid.innerHTML = slots.map(function (s) {
      var on = state.slot && state.slot.time === s.time;
      var label = s.time;
      if (state.masterId === "any" && !s.busy) {
        var m = masterById(s.masterId);
        label = s.time + " · " + (m ? m.name : "");
      }
      return '<button class="slot" type="button" role="radio" aria-checked="' + !!on + '"' +
        ' data-time="' + s.time + '"' + (s.busy ? " disabled title=\"Занято\"" : "") + ">" + esc(label) + "</button>";
    }).join("");
  }

  function resolvedMaster() {
    if (state.masterId === "any") {
      return state.slot ? masterById(state.slot.masterId) : null;
    }
    return masterById(state.masterId);
  }

  function renderConfirm() {
    var s = serviceById(state.serviceId), m = resolvedMaster();
    if (!s || !m || !state.date || !state.slot) { $("confirm-box").innerHTML = ""; return; }
    var f = contactValues();
    $("confirm-box").innerHTML = '<div class="confirm-card"><dl>' +
      "<div><dt>Услуга</dt><dd>" + esc(s.name) + " · " + s.price.toLocaleString("ru-RU") + " ₽</dd></div>" +
      "<div><dt>Мастер</dt><dd>" + esc(m.name) + "</dd></div>" +
      "<div><dt>Дата</dt><dd>" + esc(fmtDateLong(state.date)) + "</dd></div>" +
      "<div><dt>Время</dt><dd>" + esc(state.slot.time) + " · " + esc(s.dur) + "</dd></div>" +
      "<div><dt>Гость</dt><dd>" + esc(f.name || "—") + " · " + esc(f.phone || "—") + "</dd></div>" +
      (f.comment ? "<div><dt>Комментарий</dt><dd>" + esc(f.comment) + "</dd></div>" : "") +
      "</dl></div>";
  }

  function renderDone() {
    if (!lastDone) return;
    var s = serviceById(lastDone.serviceId), m = masterById(lastDone.masterId);
    $("done-box").innerHTML = '<div class="done-card"><dl>' +
      "<div><dt>Код записи</dt><dd><span class=\"booking-code\">" + esc(lastDone.code) + "</span></dd></div>" +
      "<div><dt>Услуга</dt><dd>" + esc(s ? s.name : "") + "</dd></div>" +
      "<div><dt>Мастер</dt><dd>" + esc(m ? m.name : "") + "</dd></div>" +
      "<div><dt>Когда</dt><dd>" + esc(fmtDateLong(lastDone.date)) + " · " + esc(lastDone.time) + "</dd></div>" +
      "<div><dt>Гость</dt><dd>" + esc(lastDone.name) + "</dd></div>" +
      "</dl></div>";
  }

  function renderSummary() {
    var s = serviceById(state.serviceId), m = resolvedMaster();
    $("sum-service").textContent = s ? s.name : "—";
    var mLabel = "—";
    if (state.masterId === "any") mLabel = m ? "Кто свободен (" + m.name + ")" : "Кто свободен раньше";
    else if (m) mLabel = m.name;
    $("sum-master").textContent = mLabel;
    $("sum-date").textContent = state.date ? fmtDate(state.date) : "—";
    $("sum-time").textContent = state.slot ? state.slot.time : "—";
    $("sum-price").textContent = s ? s.price.toLocaleString("ru-RU") + " ₽" : "—";
  }

  function renderStepper() {
    var items = document.querySelectorAll("#stepper li");
    items.forEach(function (li) {
      var n = +li.getAttribute("data-step");
      li.classList.toggle("is-active", n === state.step);
      li.classList.toggle("is-done", n < state.step || state.step === "done");
    });
  }

  function renderMyBookings() {
    var list = loadBookings();
    var badge = $("my-bookings-count");
    badge.hidden = list.length === 0;
    badge.textContent = list.length;
    var box = $("my-bookings"), ul = $("my-bookings-list");
    if (box.hidden) return;
    if (!list.length) {
      ul.innerHTML = "<li>Пока пусто. Пройдите запись выше — она появится здесь.</li>";
      return;
    }
    ul.innerHTML = list.map(function (b) {
      var s = serviceById(b.serviceId), m = masterById(b.masterId);
      return "<li><span><strong>" + esc(b.code) + "</strong> · " +
        esc(s ? s.name : "") + " · " + esc(m ? m.name : "") + " · " +
        esc(fmtDate(b.date)) + " " + esc(b.time) + "</span>" +
        '<button class="btn btn-ghost btn-sm" type="button" data-cancel="' + esc(b.code) + '">Отменить</button></li>';
    }).join("");
  }

  function renderHero() {
    var days = dayList(), found = [];
    for (var i = 0; i < days.length && found.length < 3; i++) {
      var slots = slotsAny(days[i].di, days[i].iso).filter(function (s) { return !s.busy; });
      for (var j = 0; j < slots.length && found.length < 3; j++) {
        found.push({ date: days[i].iso, slot: slots[j] });
      }
    }
    if (!found.length) {
      $("hero-slots").innerHTML = "<li>Всё занято — попробуйте позже</li>";
      return;
    }
    $("hero-card-date").textContent = fmtDateLong(found[0].date);
    $("hero-slots").innerHTML = found.map(function (f) {
      var m = masterById(f.slot.masterId);
      return "<li><span>" + esc(f.slot.time) + " · " + esc(fmtDate(f.date)) + "</span><span>" + esc(m ? m.name : "") + "</span></li>";
    }).join("");
  }

  function renderToday() {
    var now = new Date(), h = now.getHours() + now.getMinutes() / 60;
    var open = h >= 10 && h < 20;
    $("today-line").textContent = "Сегодня " + pad(now.getDate()) + " " + MONTHS[now.getMonth()] +
      ": " + (open ? "открыто до 20:00 — ещё успеваете сегодня-завтра." : "сейчас закрыто — откроемся в 10:00, выбирайте время заранее.");
  }

  /* ---------- навигация по шагам ---------- */
  var STEP_NAMES = { 1: "Услуга", 2: "Мастер", 3: "Дата и время", 4: "Контакты", 5: "Подтверждение" };

  function goStep(n) {
    state.step = n;
    document.querySelectorAll(".step-panel").forEach(function (p) {
      var show = (p.getAttribute("data-panel") === String(n)) || (n === "done" && p.getAttribute("data-panel") === "done");
      p.hidden = !show;
    });
    if (n === 1) renderServices();
    if (n === 2) renderMasters();
    if (n === 3) { renderDates(); renderSlots(); }
    if (n === 4) { /* форма уже в DOM */ }
    if (n === 5) renderConfirm();
    if (n === "done") renderDone();
    renderStepper(); renderSummary(); renderHero();

    var back = $("btn-back"), next = $("btn-next");
    if (n === "done") {
      back.disabled = true;
      next.textContent = "Сделать ещё одну запись";
    } else {
      back.disabled = (n === 1);
      next.textContent = (n === 5) ? "Подтвердить запись" : (n === 4 ? "К проверке →" : "Далее →");
    }
    var panel = document.querySelector('.step-panel[data-panel="' + n + '"] h3');
    if (panel) {
      var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panel.setAttribute("tabindex", "-1");
      panel.focus({ preventScroll: true });
      panel.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
    }
  }

  function contactValues() {
    return {
      name: $("f-name").value.trim(),
      phone: $("f-phone").value.trim(),
      comment: $("f-comment").value.trim(),
      consent: $("f-consent").checked
    };
  }
  function validPhone(v) {
    var d = v.replace(/\D/g, "");
    if (d.length === 11 && (d[0] === "7" || d[0] === "8")) return true;
    if (d.length === 10) return true;
    return false;
  }

  function validateStep(n) {
    var ok = true;
    function flag(id, bad) { $(id).hidden = !bad; if (bad) ok = false; }
    if (n === 1) flag("err-service", !state.serviceId);
    if (n === 2) flag("err-master", !state.masterId);
    if (n === 3) flag("err-slot", !state.slot);
    if (n === 4) {
      var f = contactValues();
      var badName = f.name.replace(/[^A-Za-zА-Яа-яЁё]/g, "").length < 2;
      var badPhone = !validPhone(f.phone);
      $("f-name").setAttribute("aria-invalid", badName);
      $("f-phone").setAttribute("aria-invalid", badPhone);
      $("err-name").hidden = !badName;
      $("err-phone").hidden = !badPhone;
      $("err-consent").hidden = f.consent;
      if (badName || badPhone || !f.consent) ok = false;
    }
    return ok;
  }

  function nextStep() {
    if (state.step === "done") { resetFlow(); goStep(1); return; }
    if (!validateStep(state.step)) {
      var err = document.querySelector('.step-panel[data-panel="' + state.step + '"] .field-error:not([hidden])');
      if (err) err.scrollIntoView({ block: "nearest", behavior: "smooth" });
      return;
    }
    if (state.step === 5) { commitBooking(); return; }
    goStep(state.step + 1);
  }

  function prevStep() {
    if (state.step === "done" || state.step <= 1) return;
    goStep(state.step - 1);
  }

  function resetFlow() {
    state.serviceId = null; state.masterId = null; state.date = null; state.slot = null;
    ["err-service", "err-master", "err-slot", "err-confirm"].forEach(function (id) { $(id).hidden = true; });
    renderServices(); renderMasters(); renderDates(); renderSlots(); renderSummary();
  }

  function commitBooking() {
    /* Повторная проверка занятости — как транзакция BEGIN IMMEDIATE у бота. */
    var m = resolvedMaster();
    if (!m || !state.date || !state.slot) { $("err-confirm").hidden = false; return; }
    if (isTaken(m.id, state.date, state.slot.time)) {
      $("err-confirm").hidden = false;
      state.slot = null;
      renderSlots(); renderSummary();
      toast("Это окно только что заняли. Выберите другое время.");
      return;
    }
    var f = contactValues();
    var code = "СК-" + Date.now().toString(36).toUpperCase().slice(-6);
    var rec = {
      code: code, serviceId: state.serviceId, masterId: m.id,
      date: state.date, time: state.slot.time,
      name: f.name, phone: f.phone, comment: f.comment,
      createdAt: new Date().toISOString()
    };
    var all = loadBookings();
    all.push(rec);
    saveBookings(all);
    lastDone = rec;
    resetFlow();
    goStep("done");
    renderMyBookings();
    toast("Готово! Демо-запись " + code + " сохранена в вашем браузере.");
  }

  /* ---------- события (делегирование) ---------- */
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-pick-service],[data-pick-master],[data-service],[data-master],[data-date],[data-time],[data-cancel]");
    if (t) {
      if (t.hasAttribute("data-pick-service")) {
        state.serviceId = +t.getAttribute("data-pick-service");
        state.masterId = state.masterId || null; state.date = null; state.slot = null;
        goStep(2);
        document.getElementById("booking").scrollIntoView({ behavior: "smooth" });
        return;
      }
      if (t.hasAttribute("data-pick-master")) {
        state.masterId = +t.getAttribute("data-pick-master");
        state.date = null; state.slot = null;
        if (!state.serviceId) { goStep(1); toast("Сначала выберите услугу."); }
        else goStep(3);
        document.getElementById("booking").scrollIntoView({ behavior: "smooth" });
        return;
      }
      if (t.hasAttribute("data-service")) {
        state.serviceId = +t.getAttribute("data-service");
        $("err-service").hidden = true;
        renderServices(); renderSummary();
        return;
      }
      if (t.hasAttribute("data-master")) {
        var mv = t.getAttribute("data-master");
        state.masterId = (mv === "any") ? "any" : +mv;
        state.date = null; state.slot = null;
        $("err-master").hidden = true;
        renderMasters(); renderSummary();
        return;
      }
      if (t.hasAttribute("data-date")) {
        state.date = t.getAttribute("data-date");
        state.slot = null;
        $("err-slot").hidden = true;
        renderDates(); renderSlots(); renderSummary();
        return;
      }
      if (t.hasAttribute("data-time") && !t.disabled) {
        var time = t.getAttribute("data-time");
        var days = dayList();
        var di = days.find(function (d) { return d.iso === state.date; }).di;
        var pool = state.masterId === "any" ? slotsAny(di, state.date) : slotsFor(state.masterId, di, state.date);
        var found = pool.find(function (s) { return s.time === time && !s.busy; });
        if (found) {
          state.slot = found;
          $("err-slot").hidden = true;
          renderSlots(); renderSummary();
        }
        return;
      }
      if (t.hasAttribute("data-cancel")) {
        var code = t.getAttribute("data-cancel");
        saveBookings(loadBookings().filter(function (b) { return b.code !== code; }));
        renderMyBookings(); renderHero();
        if (state.step === 3) { renderDates(); renderSlots(); }
        toast("Демо-запись " + code + " отменена, окно снова свободно.");
        return;
      }
    }
  });

  $("btn-next").addEventListener("click", nextStep);
  $("btn-back").addEventListener("click", prevStep);
  $("btn-reset").addEventListener("click", function () {
    resetFlow(); goStep(1);
    toast("Начали заново. Сохранённые демо-записи не тронуты.");
  });
  $("my-bookings-btn").addEventListener("click", function () {
    var box = $("my-bookings");
    box.hidden = !box.hidden;
    renderMyBookings();
    if (!box.hidden) box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  /* Ввод в форме снимает ошибки по мере исправления. */
  ["f-name", "f-phone"].forEach(function (id) {
    $(id).addEventListener("input", function (ev) {
      ev.target.setAttribute("aria-invalid", "false");
      $("err-name").hidden = true; $("err-phone").hidden = true;
    });
  });
  $("f-consent").addEventListener("change", function () { $("err-consent").hidden = true; });

  /* Мобильное меню. */
  var nav = $("site-nav"), toggle = $("nav-toggle");
  toggle.addEventListener("click", function () {
    var open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open);
    toggle.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
  });
  nav.addEventListener("click", function (e) {
    if (e.target.tagName === "A") {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });

  /* ---------- старт ---------- */
  $("year").textContent = new Date().getFullYear();
  renderCatalog();
  renderServices();
  renderMasters();
  renderSummary();
  renderHero();
  renderToday();
  renderStepper();
  renderMyBookings();
})();
