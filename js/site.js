// 共通: テーマ切り替え・メニュー・コピー・スクロール表示
(function () {
  var root = document.documentElement;
  root.classList.remove("no-js");
  try {
    var saved = localStorage.getItem("cse-theme");
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* 保存できない環境では OS の設定に従う */ }

  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var themeBtn = document.querySelector(".theme-btn");
    if (themeBtn) themeBtn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("cse-theme", next); } catch (e) { /* 無視 */ }
    });

    var toggle = document.querySelector(".nav-toggle");
    var nav = document.getElementById("nav");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
      nav.addEventListener("click", function (ev) {
        if (ev.target.closest && ev.target.closest("a")) { nav.classList.remove("open"); toggle.setAttribute("aria-expanded", "false"); }
      });
    }

    document.querySelectorAll("[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-copy");
        var label = btn.getAttribute("data-label") || btn.textContent;
        btn.setAttribute("data-label", label);
        var done = function () { btn.textContent = "コピーした"; clearTimeout(btn._t); btn._t = setTimeout(function () { btn.textContent = label; }, 1400); };
        if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
      });
    });

    // CSP で style 属性を使えないので、バーの幅は data-w から設定する
    document.querySelectorAll("[data-w]").forEach(function (el) { el.style.width = el.getAttribute("data-w") + "%"; });

    var items = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) { items.forEach(function (el) { el.classList.add("in"); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    items.forEach(function (el) { io.observe(el); });
  });
})();
