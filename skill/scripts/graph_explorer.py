#!/usr/bin/env python3
"""Generic single-file graph explorer generator (node-link graphs, stdlib only).

Usage:  python graph_explorer.py --graph <graph.json> [--out <file.html>] [--title TEXT]

Accepts {"nodes": [...], "edges": [...]} or {"nodes": [...], "links": [...]}.
Nodes may carry arbitrary extra fields; every scalar field is shown in the card.
Output is deterministic (sorted keys, no timestamps) and has no external dependencies.
Exit codes: 0 ok, 2 missing/invalid graph.
"""
import argparse
import html as _html
import json
import re
import sys
from pathlib import Path

DEFAULT_TITLE = "Graph explorer"
GROUP_FIELDS = ["domain", "origin", "community", "group"]
EDGE_KEYS = ["source", "target", "relation", "confidence", "op", "note"]


def _scalar(v):
    return isinstance(v, (str, int, float, bool)) and v is not None


def _endpoint(v):
    if isinstance(v, dict):
        v = v.get("id")
    return None if v is None else str(v)


def slim(graph):
    """Reduce the graph to what the explorer needs, with stable ordering."""
    nodes = []
    for n in graph.get("nodes", []) or []:
        if not isinstance(n, dict) or n.get("id") is None:
            continue
        d = {k: v for k, v in n.items() if _scalar(v)}
        d["id"] = str(n["id"])
        nodes.append(d)
    nodes.sort(key=lambda n: n["id"])
    raw_edges = graph.get("edges")
    if raw_edges is None:
        raw_edges = graph.get("links", [])
    edges = []
    for e in raw_edges or []:
        if not isinstance(e, dict):
            continue
        s, t = _endpoint(e.get("source")), _endpoint(e.get("target"))
        if s is None or t is None:
            continue
        d = {k: e[k] for k in e if k not in ("source", "target") and _scalar(e[k])}
        d["source"], d["target"] = s, t
        edges.append(d)
    edges.sort(key=lambda e: (e["source"], e["target"], str(e.get("relation", "")),
                              json.dumps(e, sort_keys=True)))
    group = ""
    for g in GROUP_FIELDS:
        if any(g in n for n in nodes):
            group = g
            break
    return {"nodes": nodes, "edges": edges, "group": group}


def embed_json(obj):
    """JSON safe inside <script>: no '</', no HTML comments, ASCII only (so U+2028/2029 are escaped)."""
    s = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") \
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#fff;--fg:#1b1f24;--mut:#667;--bd:#d0d7de;--ac:#0b5cad;--sf:#f6f8fa}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--fg:#e6e8ea;--mut:#9aa4ae;--bd:#2f363d;--ac:#6cb0f5;--sf:#1d2227}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{padding:10px 16px;border-bottom:1px solid var(--bd);display:flex;flex-wrap:wrap;gap:8px;align-items:center}
header h1{font-size:16px;margin:0 12px 0 0}
input,select,button{font:inherit;color:var(--fg);background:var(--sf);border:1px solid var(--bd);border-radius:4px;padding:4px 8px}
button{cursor:pointer}input[type=search]{min-width:220px;flex:1}
main{display:grid;grid-template-columns:minmax(260px,1fr) 2fr;height:calc(100vh - 56px)}
@media (max-width:760px){main{grid-template-columns:1fr;height:auto}}
#list,#card{overflow:auto;padding:8px 16px}#list{border-right:1px solid var(--bd)}
.item{padding:3px 6px;border-radius:4px;cursor:pointer;display:flex;gap:6px;justify-content:space-between}
.item:hover,.item.sel{background:var(--sf)}.tag{color:var(--mut);font-size:12px}
a.nb{color:var(--ac);cursor:pointer;text-decoration:underline}
h2{font-size:17px;margin:4px 0;word-break:break-all}h3{font-size:14px;margin:12px 0 4px}h4{font-size:13px;margin:8px 0 2px;color:var(--mut)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:6px 0}dt{color:var(--mut)}dd{margin:0;word-break:break-word}
ul{margin:2px 0;padding-left:18px}.mut{color:var(--mut)}
</style></head><body>
<header><h1>__TITLE__</h1>
<input id="q" type="search" placeholder="Search by name or id" aria-label="Search by name or id">
<select id="ft" aria-label="Type"></select><select id="fg" aria-label="Group"></select>
<span id="count" class="mut"></span></header>
<main><div id="list"></div><div id="card"><p class="mut">Pick a node from the list.</p></div></main>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
(function(){
"use strict";
var D=JSON.parse(document.getElementById("graph-data").textContent);
var MAXR=200;
var PRIO=["id","label","type","kind","data_type","nullable","purpose","purpose_source","comment","source_file","source_location","description","community","file"];
var byId={},out={},inn={},hay={};
D.nodes.forEach(function(n){byId[n.id]=n;out[n.id]=[];inn[n.id]=[];
  hay[n.id]=(n.id+"\n"+(n.label===undefined?"":n.label)).toLowerCase();});
D.edges.forEach(function(e){if(out[e.source])out[e.source].push(e);if(inn[e.target])inn[e.target].push(e);});
var $=function(i){return document.getElementById(i);};
function nm(n){return n.label!==undefined&&n.label!==""?String(n.label):n.id;}
function el(t,txt,cls){var x=document.createElement(t);if(txt!==undefined)x.textContent=txt;if(cls)x.className=cls;return x;}
function fill(sel,label,vals){sel.appendChild(new Option(label,""));vals.forEach(function(v){sel.appendChild(new Option(v,v));});}
function uniq(k){var s={};D.nodes.forEach(function(n){if(n[k]!==undefined&&n[k]!=="")s[String(n[k])]=1;});return Object.keys(s).sort();}
fill($("ft"),"All types",uniq("type"));
if(D.group)fill($("fg"),"All "+D.group,uniq(D.group));else $("fg").style.display="none";
var sel=null;
function match(n,q){
  if($("ft").value&&String(n.type)!==$("ft").value)return false;
  if(D.group&&$("fg").value&&String(n[D.group])!==$("fg").value)return false;
  return !q||hay[n.id].indexOf(q)>=0;
}
function renderList(){
  var L=$("list");L.textContent="";var shown=0,tot=0,q=$("q").value.trim().toLowerCase();
  var fr=document.createDocumentFragment();
  for(var i=0;i<D.nodes.length;i++){var n=D.nodes[i];if(!match(n,q))continue;tot++;if(shown>=MAXR)continue;shown++;
    var d=el("div",undefined,"item"+(n.id===sel?" sel":""));
    d.appendChild(el("span",nm(n)));d.appendChild(el("span",(n.type!==undefined?n.type:"")+(D.group&&n[D.group]!==undefined?" / "+n[D.group]:""),"tag"));
    d.setAttribute("data-id",n.id);fr.appendChild(d);}
  L.appendChild(fr);
  $("count").textContent=tot+" nodes"+(tot>shown?" (showing first "+shown+")":"");
}
$("list").addEventListener("click",function(ev){var t=ev.target;while(t&&t!==this&&!t.getAttribute("data-id"))t=t.parentNode;
  if(t&&t.getAttribute&&t.getAttribute("data-id"))show(t.getAttribute("data-id"));});
function nbBox(title,edges,end){
  var box=el("div");box.appendChild(el("h3",title+" ("+edges.length+")"));
  if(!edges.length){box.appendChild(el("span","none","mut"));return box;}
  var groups={},keys=[];
  edges.forEach(function(e){var r=e.relation===undefined?"(related)":String(e.relation);if(!groups[r]){groups[r]=[];keys.push(r);}groups[r].push(e);});
  keys.sort();
  keys.forEach(function(r){
    box.appendChild(el("h4",r+" ("+groups[r].length+")"));var ul=el("ul");
    groups[r].forEach(function(e){var id=e[end],n=byId[id],li=el("li");
      if(n){var a=el("a",nm(n),"nb");a.onclick=function(){show(id);};li.appendChild(a);if(n.type!==undefined)li.appendChild(el("span"," ("+n.type+")","tag"));}
      else li.appendChild(el("span",id));
      if(e.op!==undefined)li.appendChild(el("span"," ["+e.op+"]","tag"));
      ul.appendChild(li);});
    box.appendChild(ul);});
  return box;
}
function show(id){
  var n=byId[id];if(!n)return;sel=id;var C=$("card");C.textContent="";
  C.appendChild(el("h2",nm(n)));
  var dl=el("dl"),seen={};
  function row(k){if(seen[k]||n[k]===undefined||n[k]===null||n[k]==="")return;seen[k]=1;dl.appendChild(el("dt",k));dl.appendChild(el("dd",String(n[k])));}
  PRIO.forEach(row);
  Object.keys(n).sort().forEach(row);
  C.appendChild(dl);
  C.appendChild(nbBox("Incoming",inn[id]||[],"source"));
  C.appendChild(nbBox("Outgoing",out[id]||[],"target"));
  renderList();
  try{history.replaceState(null,"","#"+encodeURIComponent(id));}catch(x){}
}
var tm=null;
$("q").addEventListener("input",function(){clearTimeout(tm);tm=setTimeout(renderList,80);});
["ft","fg"].forEach(function(i){$(i).addEventListener("input",renderList);});
renderList();
var h="";try{h=decodeURIComponent(location.hash.slice(1));}catch(x){}
if(h&&byId[h])show(h);
})();
</script></body></html>
"""


def build_html(graph, title=DEFAULT_TITLE):
    data = embed_json(slim(graph))
    esc = _html.escape(str(title), quote=True)
    # single pass so neither value can inject the other's placeholder
    return re.sub(r"__TITLE__|__DATA__", lambda m: esc if m.group(0) == "__TITLE__" else data, TEMPLATE)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=DEFAULT_TITLE)
    a = ap.parse_args(argv)
    gp = Path(a.graph)
    try:
        graph = json.loads(gp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"graph_explorer: cannot read graph {gp}: {ex}", file=sys.stderr)
        return 2
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        print(f"graph_explorer: {gp} is not a node-link graph (needs a 'nodes' list)", file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else gp.with_suffix(".html")
    page = build_html(graph, a.title)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"explorer: {len(graph['nodes'])} nodes -> {out} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
