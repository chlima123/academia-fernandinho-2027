# -*- coding: utf-8 -*-
"""Verificação do painel Academia FB 2027 (apple-design, mobile-first).

Uso:
    python3 verify.py                # mede o index.html local
    python3 verify.py <url>          # mede uma URL no ar (mesmo harness)

Sai com código 1 quando qualquer prova falha.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

LOCAL = pathlib.Path(__file__).with_name("index.html")
URL = sys.argv[1] if len(sys.argv) > 1 else "file://" + str(LOCAL)
IS_LIVE = URL.startswith("http")

fails = []
def check(nome, ok, detalhe=""):
    print(("  ok   " if ok else "  FALHA") + f" · {nome}" + (f" — {detalhe}" if detalhe else ""))
    if not ok:
        fails.append(nome)

CONTRASTE = """
(() => {
  function parse(c){
    const m = c.match(/rgba?\\(([^)]+)\\)/); if(!m) return null;
    const p = m[1].split(",").map(Number);
    return {r:p[0], g:p[1], b:p[2], a:(p.length>3?p[3]:1)};
  }
  function lum(c){
    const f = v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); };
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);
  }
  function over(fg, bg){
    const a = fg.a;
    return {r: fg.r*a + bg.r*(1-a), g: fg.g*a + bg.g*(1-a), b: fg.b*a + bg.b*(1-a), a:1};
  }
  function bgOf(el){
    let stack = [], n = el;
    while(n && n.nodeType === 1){
      const c = parse(getComputedStyle(n).backgroundColor);
      if(c && c.a > 0){ stack.push(c); if(c.a >= 0.999) break; }
      n = n.parentElement;
    }
    let base = {r:255,g:255,b:255,a:1};
    for(let i = stack.length-1; i >= 0; i--){ base = over(stack[i], base); }
    return base;
  }
  const out = [];
  const sel = "p,h1,h2,h3,li,span.mk,b,em,.v,.val,.an,.av,.cv,.d,.l,.n,.ts,.num,.eyebrow," +
              ".lede,.pname,.ptag,.padd,.pnote,.q,.tlink,a,.chip,.tab,.brand,.badge,.note," +
              ".disclaimer,.micro,.delta,.tel,footer,.hint,.legend";
  document.querySelectorAll(sel).forEach(el => {
    const own = Array.from(el.childNodes).filter(n => n.nodeType===3 && n.textContent.trim().length>1);
    if(!own.length) return;
    const cs = getComputedStyle(el);
    if(cs.visibility === "hidden" || cs.display === "none") return;
    const r = el.getBoundingClientRect(); if(!r.width || !r.height) return;
    const fg = parse(cs.color); if(!fg) return;
    const bg = bgOf(el);
    const c = over(fg, bg);
    const l1 = lum(c), l2 = lum(bg);
    const ratio = (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    const large = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 600);
    const need = large ? 3 : 4.5;
    if(ratio < need){
      out.push({t: el.textContent.trim().slice(0,52), ratio: +ratio.toFixed(2), need: need,
                cls: el.className && el.className.baseVal === undefined ? el.className : el.tagName});
    }
  });
  return out;
})()
"""

TARGETS = """
(() => {
  const bad = [];
  document.querySelectorAll("button, a, input, [role=tab]").forEach(el => {
    const r = el.getBoundingClientRect();
    if(!r.width || !r.height) return;
    if(el.closest("[hidden]")) return;
    const cs = getComputedStyle(el);
    if(cs.display === "none" || cs.visibility === "hidden") return;
    // links inline dentro de parágrafo não são alvo de toque isolado
    if(el.tagName === "A" && el.parentElement && /^(P|LI|FOOTER|SPAN|DIV)$/.test(el.parentElement.tagName)
       && cs.display === "inline") return;
    if(r.height < 40){ bad.push({t: (el.textContent||"").trim().slice(0,30) || el.id || el.tagName,
                                 h: Math.round(r.height)}); }
  });
  return bad;
})()
"""

def overflow(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    erros = []

    # ---------------------------------------------------------------- mobile
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                    is_mobile=True, has_touch=True)
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.on("console", lambda m: erros.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(800)

    print("== conteúdo")
    check("title", "Academia Fernandinho Beltrão" in pg.title(), pg.title())
    for sel, n in ((".kpi", 5), ('article.prow', 5), (".tcard", 4), (".rule", 4),
                   (".area", 4), (".lk", 3), (".tab", 6), (".chip[data-plan]", 5),
                   (".mplan", 5), (".mx .rh", 13), (".mx .hd", 6)):
        got = pg.eval_on_selector_all(sel, "e=>e.length")
        check(f"{sel} = {n}", got == n, f"achei {got}")

    check("matriz no celular visível, tabela escondida",
          pg.is_visible(".mxm") and not pg.is_visible(".mxwrap"))
    vis = pg.eval_on_selector_all(".mplan", "els=>els.filter(e=>!e.hidden && e.offsetParent).length")
    check("um painel de plano visível por vez", vis == 1, f"{vis} visíveis")

    print("== barra inferior")
    st = pg.evaluate("""() => {
      const n = document.querySelector('.tabbar'), r = n.getBoundingClientRect();
      const cs = getComputedStyle(n);
      return {pos: cs.position, bottom: Math.round(r.bottom), vh: window.innerHeight,
              display: cs.display, blur: cs.backdropFilter};
    }""")
    check("tab bar fixa no rodapé", st["pos"] == "fixed" and abs(st["bottom"] - st["vh"]) <= 1, str(st))
    check("tab bar com material translúcido", "blur" in (st["blur"] or ""), st["blur"])

    hdr = pg.evaluate("""() => {
      const h = document.querySelector('#bar'), r = h.getBoundingClientRect();
      return {pos: getComputedStyle(h).position, top: Math.round(r.top),
              h: Math.round(r.height)};
    }""")
    check("barra do topo sticky", hdr["pos"] == "sticky" and hdr["top"] == 0, str(hdr))
    pg.evaluate("window.scrollTo(0, 900)")
    pg.wait_for_timeout(500)
    hdr2 = pg.evaluate("() => ({top: Math.round(document.querySelector('#bar').getBoundingClientRect().top), y: window.scrollY})")
    check("barra continua no topo ao rolar", hdr2["top"] == 0 and hdr2["y"] > 500, str(hdr2))
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(300)

    print("== controle segmentado (mês/ano)")
    seg = pg.evaluate("""() => {
      const s = document.querySelector('#seg-mes'), t = s.querySelector('.seg-thumb'),
            b = s.querySelector('[aria-selected="true"]');
      const tr = t.getBoundingClientRect(), br = b.getBoundingClientRect();
      return {w: Math.round(tr.width), bw: Math.round(br.width),
              dx: Math.round(tr.left - br.left), txt: t.textContent.length};
    }""")
    check("indicador mede o botão ativo", seg["w"] > 20 and abs(seg["dx"]) <= 2
          and abs(seg["w"] - seg["bw"]) <= 2, str(seg))
    check("indicador não interfere na árvore acessível", seg["txt"] == 0)

    p_mes = pg.eval_on_selector_all(".prow .pval", "e=>e.map(x=>x.textContent)")
    pg.click('#seg-mes button[data-modo="ano"]')
    pg.wait_for_timeout(500)
    p_ano = pg.eval_on_selector_all(".prow .pval", "e=>e.map(x=>x.textContent)")
    un_ano = pg.eval_on_selector_all(".prow .punit", "e=>e.map(x=>x.textContent)")
    nota = pg.text_content("#ladder-note") or ""
    check("mensal x anual troca os valores",
          p_mes[0] == "R$ 200" and p_ano[0] == "R$ 2.400" and p_ano[-1] == "R$ 18.000",
          f"{p_mes[0]} → {p_ano[0]} … {p_ano[-1]}")
    check("unidade vira /ano e a nota acompanha",
          set(un_ano) == {"/ano"} and "12 mensalidades" in nota)
    seg2 = pg.evaluate("""() => {
      const s = document.querySelector('#seg-mes'), t = s.querySelector('.seg-thumb'),
            b = s.querySelector('[aria-selected="true"]');
      return Math.round(t.getBoundingClientRect().left - b.getBoundingClientRect().left);
    }""")
    check("indicador acompanha o novo botão", abs(seg2) <= 2, str(seg2))
    pg.click('#seg-mes button[data-modo="mes"]')
    pg.wait_for_timeout(400)

    print("== matriz no celular")
    pg.click('.chip[data-plan="Flash"]')
    pg.wait_for_timeout(250)
    txt_flash = pg.text_content('.mplan[data-plan="Flash"]') or ""
    check("chip Flash mostra a lista do Flash",
          "Foco intensivo nas 4 matérias do 2º dia" in txt_flash
          and "Mentoria Geral" in txt_flash)
    off = pg.eval_on_selector_all('.mplan[data-plan="Flash"] li.off', "e=>e.length")
    check("itens não inclusos aparecem marcados", off == 10, f"{off} linhas 'off'")
    pg.click('.chip[data-plan="Super"]')
    pg.wait_for_timeout(250)
    vis2 = pg.eval_on_selector_all(".mplan", "els=>els.filter(e=>!e.hidden).length")
    check("troca de plano mantém um painel", vis2 == 1)

    print("== tema")
    base = pg.evaluate("() => ({theme: document.documentElement.dataset.theme, bg: getComputedStyle(document.body).backgroundColor})")
    pg.click("#theme")
    pg.wait_for_timeout(350)
    alt = pg.evaluate("() => ({theme: document.documentElement.dataset.theme, bg: getComputedStyle(document.body).backgroundColor})")
    check("botão alterna o tema", base["theme"] != alt["theme"] and base["bg"] != alt["bg"],
          f'{base["theme"]} → {alt["theme"]}')
    persist = pg.evaluate("() => localStorage.getItem('afb-theme')")
    check("tema persistido", persist == alt["theme"], str(persist))
    fora = pg.evaluate(CONTRASTE)
    check("contraste AA no tema escuro", len(fora) == 0, str(fora[:5]))
    pg.click("#theme")
    pg.wait_for_timeout(350)
    fora2 = pg.evaluate(CONTRASTE)
    check("contraste AA no tema claro", len(fora2) == 0, str(fora2[:5]))

    print("== alvos de toque (390px)")
    alvos = pg.evaluate(TARGETS)
    check("todo botão/aba/link isolado ≥ 40px", len(alvos) == 0, str(alvos[:6]))

    print("== overflow")
    for w in (320, 360, 390, 430, 768, 1024, 1280):
        pg.set_viewport_size({"width": w, "height": 900})
        pg.wait_for_timeout(220)
        ov = overflow(pg)
        check(f"scrollWidth == innerWidth @{w}", ov == 0, f"excesso {ov}px")
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(300)

    print("== navegação")
    pg.click('.tab[href="#otavio"]')
    pg.wait_for_timeout(900)
    st2 = pg.evaluate("""() => {
      const t = document.querySelector('.tab[href="#otavio"]'),
            s = document.getElementById('otavio').getBoundingClientRect();
      return {on: t.classList.contains('on'), top: Math.round(s.top),
              barh: parseInt(getComputedStyle(document.documentElement).getPropertyValue('--barh'))};
    }""")
    check("aba ativa acompanha a rolagem", st2["on"], str(st2))
    check("seção não fica sob a barra", st2["top"] >= st2["barh"] - 8, str(st2))

    print("== reduced motion")
    pg.emulate_media(reduced_motion="reduce")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(500)
    visiveis = pg.eval_on_selector_all(".mplan", "els=>els.filter(e=>!e.hidden).length")
    check("reduced motion não abre todos os painéis", visiveis == 1, f"{visiveis}")
    seg3 = pg.evaluate("""() => {
      const s = document.querySelector('#seg-mes'), t = s.querySelector('.seg-thumb'),
            b = s.querySelector('[aria-selected="true"]');
      return Math.round(t.getBoundingClientRect().left - b.getBoundingClientRect().left);
    }""")
    check("indicador posicionado sem animar", abs(seg3) <= 2, str(seg3))
    pg.emulate_media(reduced_motion="no-preference")

    print("== capturas")
    pg.evaluate("() => { document.documentElement.style.scrollBehavior='auto'; }")
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(600)
    pg.screenshot(path="shot-mobile.png")
    pg.evaluate("document.querySelector('#planos').scrollIntoView()")
    pg.wait_for_timeout(500)
    pg.screenshot(path="shot-mobile-planos.png")
    pg.evaluate("document.querySelector('#matriz').scrollIntoView()")
    pg.wait_for_timeout(500)
    pg.screenshot(path="shot-mobile-matriz.png")
    pg.evaluate("document.querySelector('#otavio').scrollIntoView()")
    pg.wait_for_timeout(500)
    pg.screenshot(path="shot-mobile-otavio.png")

    pg.set_viewport_size({"width": 1280, "height": 900})
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(500)
    pg.screenshot(path="shot-top.png")
    pg.evaluate("document.querySelector('#planos').scrollIntoView()")
    pg.wait_for_timeout(500)
    pg.screenshot(path="shot-planos.png")

    check("sem erro de página/console", len(erros) == 0, str(erros[:4]))
    b.close()

print()
if fails:
    print("FALHOU:", len(fails), "prova(s):", fails)
    sys.exit(1)
print("OK — todas as provas passaram")
