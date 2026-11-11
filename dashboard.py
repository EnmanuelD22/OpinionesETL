"""Dashboard local de KPIs del DW: python dashboard.py (http://127.0.0.1:8765)."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from sqlalchemy import case, func, select

from infrastructure.database import get_dw_engine
from infrastructure.persistence.warehouse import DimFecha, DimProducto, FactOpinion


def obtener_kpis(engine):
    consulta = (
        select(DimProducto.IdProducto, DimProducto.Nombre.label("producto"),
               DimFecha.AnioMes.label("periodo"),
               func.count().label("total"),
               func.sum(case((FactOpinion.IdClasificacion == 1, 1), else_=0)).label("positivas"),
               func.sum(case((FactOpinion.IdClasificacion == 2, 1), else_=0)).label("negativas"),
               func.sum(case((FactOpinion.IdClasificacion == 3, 1), else_=0)).label("neutras"))
        .join(DimProducto, FactOpinion.IdProducto == DimProducto.IdProducto)
        .join(DimFecha, FactOpinion.IdFecha == DimFecha.IdFecha)
        .group_by(DimProducto.IdProducto, DimProducto.Nombre, DimFecha.AnioMes)
        .order_by(DimFecha.AnioMes, DimProducto.Nombre)
    )
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(consulta).mappings()]


HTML = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opiniones · Indicadores</title>
<style>
body{font:16px system-ui;background:#f4f6f9;color:#152238;margin:0;padding:2rem;max-width:1100px;margin:auto}
h1{margin-bottom:.3rem}p{color:#536275}select{padding:.6rem;border:1px solid #aaa;border-radius:6px;margin-right:1rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin:1.5rem 0}
.card,section{background:white;border-radius:10px;padding:1.2rem;box-shadow:0 1px 5px #d8dce3}
.value{font-size:2rem;font-weight:700}.row{display:flex;align-items:center;gap:1rem;margin:.65rem 0}
.label{width:100px}.bar{height:18px;background:#3168ad;border-radius:3px;min-width:2px}
table{width:100%;border-collapse:collapse}th,td{padding:.6rem;text-align:left;border-bottom:1px solid #e4e7eb}
@media(max-width:600px){body{padding:1rem}table{font-size:.85rem}}
</style>
<h1>Análisis de opiniones</h1><p>Indicadores calculados desde OpinionesDW. Satisfacción = positivas / clasificadas.</p>
<label>Producto <select id="producto"></select></label><label>Mes <select id="mes"></select></label>
<div class="cards"><div class="card">Opiniones<div class="value" id="total">0</div></div>
<div class="card">Satisfacción<div class="value" id="satisfaccion">0%</div></div>
<div class="card">Positivas<div class="value" id="positivas">0</div></div>
<div class="card">Negativas<div class="value" id="negativas">0</div></div></div>
<section><h2>Tendencia mensual</h2><div id="tendencia"></div></section><br>
<section><h2>Detalle por producto y mes</h2><table><thead><tr><th>Producto</th><th>Mes</th><th>Opiniones</th><th>Satisfacción</th></tr></thead><tbody id="detalle"></tbody></table></section>
<script>
let datos=[];const producto=document.querySelector('#producto'),mes=document.querySelector('#mes');
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function opciones(el,valores,etiquetas={}){el.innerHTML='<option value="">Todos</option>'+valores.map(v=>`<option value="${esc(v)}">${esc(etiquetas[v]||v)}</option>`).join('')}
function mostrar(){let filas=datos.filter(d=>(!producto.value||d.IdProducto==producto.value)&&(!mes.value||d.periodo==mes.value));
let total=filas.reduce((s,d)=>s+d.total,0),pos=filas.reduce((s,d)=>s+d.positivas,0),neg=filas.reduce((s,d)=>s+d.negativas,0);
document.querySelector('#total').textContent=total;document.querySelector('#positivas').textContent=pos;
document.querySelector('#negativas').textContent=neg;document.querySelector('#satisfaccion').textContent=total?(100*pos/total).toFixed(1)+'%':'0%';
let periodos={};for(let d of filas){periodos[d.periodo]??={total:0,pos:0};periodos[d.periodo].total+=d.total;periodos[d.periodo].pos+=d.positivas}
document.querySelector('#tendencia').innerHTML=Object.entries(periodos).sort().map(([p,v])=>`<div class="row"><span class="label">${esc(p)}</span><div class="bar" style="width:${Math.max(2,100*v.pos/v.total)}%"></div><span>${(100*v.pos/v.total).toFixed(1)}%</span></div>`).join('')||'Sin datos';
document.querySelector('#detalle').innerHTML=filas.map(d=>`<tr><td>${esc(d.producto)} (#${d.IdProducto})</td><td>${esc(d.periodo)}</td><td>${d.total}</td><td>${(100*d.positivas/d.total).toFixed(1)}%</td></tr>`).join('')}
fetch('/api/kpis').then(r=>r.json()).then(d=>{datos=d;let nombres=Object.fromEntries(d.map(x=>[x.IdProducto,x.producto+' (#'+x.IdProducto+')']));opciones(producto,[...new Set(d.map(x=>x.IdProducto))].sort((a,b)=>a-b),nombres);
opciones(mes,[...new Set(d.map(x=>x.periodo))].sort());mostrar()});producto.onchange=mostrar;mes.onchange=mostrar;
</script></html>"""


def main():
    engine = get_dw_engine()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/kpis":
                body = json.dumps(obtener_kpis(engine), ensure_ascii=False).encode("utf-8")
                mime = "application/json"
            elif self.path == "/":
                body = HTML.encode("utf-8")
                mime = "text/html"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    try:
        print("Dashboard: http://127.0.0.1:8765")
        HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
