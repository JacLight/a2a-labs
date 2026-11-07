"""Builds index.html: every lab's tutorial, code and sample output on one reading page. Run after changing a lab."""
import html, re
from pathlib import Path
import markdown

HERE = Path(__file__).parent
e = html.escape
labs = []
for md in sorted(HERE.glob('lab[0-9][0-9].md')):
    n = md.stem[3:]
    src = md.read_text()
    title = re.sub(r'^# Lab \d+:\s*', '', src.splitlines()[0])
    body = markdown.markdown('\n'.join(src.splitlines()[1:]), extensions=['fenced_code'])
    body = body.replace('<h2>', '<h3>').replace('</h2>', '</h3>')
    py = next(HERE.glob(f'lab{n}_*.py'))
    out = HERE / 'out' / f'lab{n}.txt'
    labs.append((n, title, body, py.name, py.read_text(), out.read_text() if out.exists() else ''))

nav = ''.join(f'<a href="#lab{n}"><b>{n}</b>{e(t)}</a>' for n, t, *_ in labs)
cards = ''.join(f'''<section id="lab{n}"><p class="k">LAB {n}</p><h2>{e(t)}</h2>{b}
<details><summary>The code <code>{e(f)}</code></summary><pre>{e(code)}</pre></details>
<details><summary>Sample output <code>out/lab{n}.txt</code></summary><pre class="out">{e(o)}</pre></details></section>'''
                for n, t, b, f, code, o in labs)
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A2A labs</title><style>
:root{{--bg:#fbfaf7;--fg:#1d2433;--muted:#6b7280;--line:#e5e2da;--pane:#f4f2ec;--accent:#b45309;--code:#fffdf8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15171b;--fg:#e8e6e1;--muted:#9aa0a6;--line:#2c2f36;--pane:#1b1e23;--accent:#f59e0b;--code:#111317}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,Inter,system-ui,sans-serif}}
.wrap{{display:grid;grid-template-columns:260px 1fr;max-width:1240px;margin:0 auto}}
nav{{position:sticky;top:0;height:100vh;overflow:auto;padding:26px 14px;border-right:1px solid var(--line)}}
nav a{{display:flex;gap:10px;padding:7px 8px;border-radius:8px;color:var(--fg);text-decoration:none;font-size:14px;line-height:1.35}}
nav a:hover{{background:var(--pane)}} nav b{{color:var(--accent);font:600 13px/1.35 ui-monospace,monospace;flex:none}}
main{{padding:30px 34px 80px;min-width:0}} h1{{font-size:28px;margin:0 0 6px}} .lede{{color:var(--muted);max-width:760px}}
section{{border-top:1px solid var(--line);padding:26px 0 8px}} .k{{margin:0;color:var(--accent);font:600 12px/1 ui-monospace,monospace;letter-spacing:.08em}}
h2{{margin:6px 0 4px;font-size:22px}} h3{{font-size:15px;margin:18px 0 4px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
code{{font:14px ui-monospace,"JetBrains Mono",monospace;background:var(--pane);padding:1px 5px;border-radius:5px}}
pre{{background:var(--code);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow:auto;font:13px/1.5 ui-monospace,"JetBrains Mono",monospace}}
pre code{{background:none;padding:0}} pre.out{{max-height:420px}}
details{{margin:10px 0}} summary{{cursor:pointer;font-weight:600}} summary code{{font-weight:400}}
@media (max-width:820px){{.wrap{{grid-template-columns:1fr}} nav{{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}} main{{padding:20px 16px 60px}}}}
</style></head><body><div class="wrap"><nav>{nav}</nav><main>
<h1>A2A labs</h1>
<p class="lede">Short tutorials you can run, one for each section of the video where code helps. Each one uses the official Python SDK (a2a-sdk 1.3.0), starts its own server on your machine, prints what happened and stops.</p>
<h3>Set up once</h3><pre>cd a2a/labs
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python lab06_serve.py</pre>
{cards}</main></div></body></html>'''
(HERE / 'index.html').write_text(page)
print(len(labs), 'labs ->', HERE / 'index.html')
