"""Экспорт страницы academic в PDF: mkdocs build -> print-вёрстка -> headless Chrome."""
import os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(r"C:\Users\Aleksandr Riabkov\Desktop\Itmo.py\Labs\AR-portfolio-site")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "academic.pdf"
PAGE_URL = "https://ar-git-hub.github.io/AR-portfolio-site/achievements/academic/"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

FULL_NAME = "Рябков Александр Владиславович"
SITE_URL = "https://ar-git-hub.github.io/AR-portfolio-site/"
CONTACTS = [  # (подпись, ссылка) — взято со страницы «Обратная связь» сайта
    ("Telegram: @ar_arararar", "https://t.me/ar_arararar"),
    ("riabkovsasha2707@gmail.com", "mailto:riabkovsasha2707@gmail.com"),
    ("github.com/AR-git-hub", "https://github.com/AR-git-hub"),
    ("Сайт-портфолио", SITE_URL),
]
CONTACTS_HTML = " &nbsp;·&nbsp; ".join(f'<a href="{u}">{t}</a>' for t, u in CONTACTS)

CSS = r"""
@page { size: A4; margin: 14mm 15mm; }
html, body { background:#fff !important; margin:0; }
body > *:not(#print) { display:none !important; }
#print { width:180mm; font: 11pt/1.45 "Segoe UI", Roboto, Arial, sans-serif; color:#111; }
#print h1 { font-size:24pt; margin:0 0 1mm; }
#print .name { font-size:14pt; font-weight:600; margin:0 0 1.5mm; }
#print .contacts { font-size:9.5pt; margin:0 0 3mm; }
#print .head { margin-bottom:4mm; }
#print .foot { margin-top:8mm; border-top:2px solid #303f9f; padding-top:3mm; }
#print .foot .name { margin-bottom:2mm; }
#print h2 { font-size:15pt; margin:7mm 0 2mm; color:#303f9f; border-bottom:1px solid #c5cae9; padding-bottom:1mm; }
#print h3 { font-size:12.5pt; margin:5mm 0 1.5mm; }
#print .t { margin:0 0 2mm; }
#print .li { position:relative; padding-left:5mm; }
#print .li.first::before { content:"•"; position:absolute; left:0; color:#303f9f; }
#print a { color:#1a55c8; text-decoration:underline; }
#print .headerlink { display:none; }
#print .keep, #print .fig, #print .row, #print h2, #print h3 { break-inside:avoid; page-break-inside:avoid; }
#print h2, #print h3 { break-after:avoid; }
#print .fig, #print .row { margin:1mm 0 3mm; text-align:center; }
#print img { display:inline-block; max-width:100%; object-fit:contain; border-radius:2px; }
#print .keep .fig img { max-height:105mm; }
#print .fig img { max-height:125mm; }
#print .row { display:flex; gap:3mm; justify-content:center; align-items:flex-start; }
#print .row img { min-width:0; flex:1 1 0; max-height:80mm; }
"""

JS = r"""
(() => {
  const BASE = %s, HEAD = %s, FOOT = %s;
  const art = document.querySelector('article.md-content__inner');
  art.querySelectorAll('.md-content__button, .headerlink').forEach(e => e.remove());
  // абсолютные ссылки (файлы на GitHub Pages), чтобы они работали из PDF
  art.querySelectorAll('a[href]').forEach(a => {
    const h = a.getAttribute('href');
    if (h && !/^(https?:|mailto:|#)/.test(h)) a.href = new URL(h, BASE).href;
  });

  // Линеаризация: заголовки, текстовые фрагменты и картинки/ряды картинок
  const items = [];
  const isImg = n => n.nodeType === 1 && n.tagName === 'IMG';
  function flushInline(nodes, li) {
    while (nodes.length && nodes[0].nodeType === 3 && !nodes[0].textContent.trim()) nodes.shift();
    while (nodes.length && nodes.at(-1).nodeType === 3 && !nodes.at(-1).textContent.trim()) nodes.pop();
    if (!nodes.length) return;
    const d = document.createElement('div');
    d.className = 't' + (li ? ' li' + (li.first ? ' first' : '') : '');
    nodes.forEach(n => d.appendChild(n.cloneNode(true)));
    if (li) li.first = false;
    items.push({ kind: 'text', el: d });
  }
  function walkInline(parent, li) {
    const kids = [...parent.childNodes];
    let buf = [];
    for (let i = 0; i < kids.length; i++) {
      const n = kids[i];
      if (isImg(n)) {
        flushInline(buf, li); buf = [];
        const group = [n];  // картинки подряд без перевода строки -> один ряд
        while (i + 1 < kids.length && isImg(kids[i + 1])) group.push(kids[++i]);
        items.push({ kind: 'img', imgs: group });
      } else if (n.nodeType === 1 && /^(P|UL|OL|LI|DIV)$/.test(n.tagName)) {
        flushInline(buf, li); buf = [];
        walkBlock(n, li);
      } else buf.push(n);
    }
    flushInline(buf, li);
  }
  function walkBlock(el, li) {
    if (el.tagName === 'H1') return;  // титул страницы не нужен: сверху шапка резюме
    if (/^H[1-6]$/.test(el.tagName)) { items.push({ kind: 'h', el: el.cloneNode(true) }); return; }
    if (el.tagName === 'UL' || el.tagName === 'OL') { [...el.children].forEach(c => walkBlock(c, li)); return; }
    if (el.tagName === 'LI') { walkInline(el, { first: true }); return; }
    if (el.tagName === 'P' || el.tagName === 'DIV') { walkInline(el, li); return; }
    items.push({ kind: 'text', el: el.cloneNode(true) });
  }
  [...art.children].forEach(c => walkBlock(c, null));

  const figOf = it => {
    const d = document.createElement('div');
    d.className = it.imgs.length > 1 ? 'row' : 'fig';
    it.imgs.forEach(im => { const c = im.cloneNode(); c.removeAttribute('loading'); d.appendChild(c); });
    return d;
  };

  // Сборка: [заголовки + текст достижения + первая картинка] -> один неразрывный блок
  const root = document.createElement('div'); root.id = 'print';
  let pending = [];      // заголовки/текст, ещё не привязанные к картинке
  let hadImg = false;    // уже была картинка после последнего текста
  const flushPending = () => {  // заголовок не отрываем от текста под ним
    if (!pending.length) return;
    const k = document.createElement('div'); k.className = 'keep';
    pending.forEach(e => k.appendChild(e)); root.appendChild(k); pending = [];
  };
  for (const it of items) {
    if (it.kind === 'h') {
      flushPending(); pending.push(it.el); hadImg = false;
    } else if (it.kind === 'text') {
      if (hadImg) { flushPending(); hadImg = false; }
      pending.push(it.el);
    } else if (!hadImg && pending.length) {
      flushPending(); root.lastChild.appendChild(figOf(it)); hadImg = true;
    } else {
      flushPending(); root.appendChild(figOf(it)); hadImg = true;
    }
  }
  flushPending();
  root.insertAdjacentHTML('afterbegin', HEAD);
  root.insertAdjacentHTML('beforeend', FOOT);
  document.body.appendChild(root);
  document.documentElement.setAttribute('data-md-color-scheme', 'default');
  document.body.style.margin = '0';

  // Раскладка по страницам: картинку, которая почти влезает, ужимаем до остатка
  // страницы; если придётся ужать сильнее, чем до 40%%, переносим блок целиком.
  const MM = 96 / 25.4, PAGE = 269 * MM, SLACK = 4 * MM, MIN_IMG = 50 * MM;
  // клоны картинок добавлены до onload, поэтому к load они уже загружены
  window.addEventListener('load', () => {
    const top0 = root.getBoundingClientRect().top;
    let pageStart = 0, prevPics = null;   // картинки предыдущего блока на этой странице
    const heightOf = pics => Math.max(...pics.map(i => i.getBoundingClientRect().height));
    for (const el of [...root.children]) {
      if (el.classList.contains('foot')) continue;   // контакты пусть встают сами
      const r = el.getBoundingClientRect();
      const top = r.top - top0 - pageStart, bottom = r.bottom - top0 - pageStart;
      const pics = [...el.querySelectorAll('img')];
      if (bottom <= PAGE - SLACK) { prevPics = pics.length ? pics : null; continue; }
      // текст без картинки не влез: пробуем ужать картинку над ним
      if (!pics.length && prevPics) {
        const h = heightOf(prevPics), t = h - (bottom - (PAGE - SLACK));
        if (t >= Math.max(0.6 * h, MIN_IMG)) {
          prevPics.forEach(i => i.style.maxHeight = t + 'px');
          if (el.getBoundingClientRect().bottom - top0 - pageStart <= PAGE - SLACK) { prevPics = null; continue; }
        }
      }
      const figH = pics.length ? heightOf(pics) : 0;
      const target = figH - (bottom - (PAGE - SLACK));
      if (pics.length && top < PAGE && target >= Math.max(0.4 * figH, MIN_IMG)) {
        pics.forEach(i => i.style.maxHeight = target + 'px');
        const nb = el.getBoundingClientRect().bottom - top0 - pageStart;
        if (nb <= PAGE - SLACK) { prevPics = pics; continue; }
      }
      el.style.breakBefore = 'page';
      el.style.marginTop = '0';
      pageStart = el.getBoundingClientRect().top - top0;
      prevPics = pics.length ? pics : null;
    }
  });
})();
"""


def main():
    tmp = Path(tempfile.mkdtemp())
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    subprocess.run([str(REPO / "venv/Scripts/mkdocs.exe"), "build", "-q", "-d", str(tmp / "site")],
                   cwd=REPO / "source", env=env, check=True)
    page = tmp / "site/achievements/academic/index.html"
    html = page.read_text(encoding="utf8")
    import json
    html = html.replace('loading="lazy"', "")
    html = html.replace("</head>", f"<style>{CSS}</style></head>")
    head = (f'<div class="head keep"><h1>Резюме</h1>'
            f'<div class="name">{FULL_NAME}</div>'
            f'<div class="contacts">{CONTACTS_HTML}</div></div>')
    foot = (f'<div class="foot keep"><div class="name">Контакты — {FULL_NAME}</div>'
            f'<div class="contacts">{CONTACTS_HTML}</div></div>')
    args = tuple(json.dumps(x) for x in (PAGE_URL, head, foot))
    html = html.replace("</body>", f"<script>{JS % args}</script></body>")
    page.write_text(html, encoding="utf8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=15000",
                    f"--user-data-dir={tmp / 'chrome'}", f"--print-to-pdf={OUT}", page.as_uri()],
                   check=True, capture_output=True)
    print("PDF:", OUT)


if __name__ == "__main__":
    main()
