# html_builder/timeline.py
# Génère le graphique timeline (Gantt) des exécutions de scénarios par projet.
# Visualise les exécutions simultanées pour détecter les conflits de ressources.

import json
import pandas as pd

from config import COL_PROJECT_ID, COL_RUN_STATUS


def build_timeline_html(df: pd.DataFrame) -> str:
    """
    Génère le composant timeline auto-contenu (HTML + JS inline).

    Chaque jour est rendu avec :
      - Une ligne par projet (barres de tous les scénarios overlaid)
      - Drill-down par clic : une sous-ligne par scénario
      - Sélecteur de jour (7 derniers jours)
      - Ligne "NOW" si on visualise aujourd'hui

    Args:
        df : DataFrame issu de prepare_timeline_data() avec colonnes :
             project_id, scenario_id, run_id, run_status,
             run_day, start_s, end_s, run_duration_s

    Returns:
        str : HTML + JS inline prêt à insérer dans le body.
    """
    if df.empty:
        return ""

    df = df.copy()
    if "scenario_id" in df.columns:
        df["scenario_id"] = df["scenario_id"].fillna("unknown").astype(str)

    # ── Construction du dict de données JS ───────────────────────────────────
    # Structure : {day: {project: {scenario: [{s, e, d, st}]}}}
    days_data: dict = {}
    for row in df.to_dict("records"):
        day  = str(row["run_day"])
        proj = str(row[COL_PROJECT_ID])
        scen = str(row.get("scenario_id", "?"))
        days_data.setdefault(day, {}).setdefault(proj, {}).setdefault(scen, [])
        days_data[day][proj][scen].append({
            "s":  int(round(float(row["start_s"]))),
            "e":  int(round(float(row["end_s"]))),
            "d":  int(round(float(row["run_duration_s"]))),
            "st": str(row[COL_RUN_STATUS]).lower(),
        })

    sorted_days   = sorted(days_data.keys(), reverse=True)
    default_day   = sorted_days[0] if sorted_days else ""
    js_data       = json.dumps(days_data,  ensure_ascii=False, separators=(",", ":"))
    sorted_days_j = json.dumps(sorted_days, ensure_ascii=False)
    default_day_j = json.dumps(default_day)

    script = (
        "<script>\n(function(){\n"
        "const D="    + js_data       + ";\n"
        "const DAYS=" + sorted_days_j + ";\n"
        "let cur="    + default_day_j + ";\n"
        "let expanded={};\n"
        "let viewStart=0,viewEnd=86400;\n"
        "let zoomSetupDone=false;\n"
        + _JS_BODY
        + "\n})();\n</script>\n"
    )

    return _HTML_SKELETON + script


# ── Squelette HTML ────────────────────────────────────────────────────────────

_HTML_SKELETON = """
    <div class="container" style="margin-bottom:30px;">
        <div class="section-topbar">
            <div class="section-header">
                <h2 class="section-title">Execution Timeline</h2>
                <span class="section-badge">Concurrency View</span>
            </div>
            <div id="tl-day-btns" class="filter-bar"></div>
        </div>
        <div class="chart-card" style="overflow:hidden;padding:0;">
            <div id="tl-wrapper" style="padding:0 0 12px;"></div>
        </div>
    </div>
    <div id="tl-tt" style="
        position:fixed;z-index:9999;pointer-events:none;
        background:white;border:1px solid var(--border);
        border-radius:12px;padding:12px 16px;
        box-shadow:0 12px 32px rgba(0,0,0,.10),0 2px 8px rgba(0,0,0,.06);
        min-width:190px;opacity:0;transition:opacity .15s ease;
        font-family:'Inter',sans-serif;
    "></div>
"""

# ── Corps JavaScript ──────────────────────────────────────────────────────────
# Pas de f-string : les ${...} des template literals JS sont des caractères littéraux.

_JS_BODY = """
// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtTime(s){
    const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);
    return ('0'+h).slice(-2)+':'+('0'+m).slice(-2);
}
function fmtDur(s){
    s=Math.round(s);
    if(s<60)  return s+'s';
    if(s<3600)return Math.floor(s/60)+'m '+('0'+(s%60)).slice(-2)+'s';
    return Math.floor(s/3600)+'h '+('0'+Math.floor((s%3600)/60)).slice(-2)+'m';
}
function isToday(d){ return new Date().toISOString().slice(0,10)===d; }
function nowSecs(){
    const n=new Date();
    return n.getHours()*3600+n.getMinutes()*60+n.getSeconds();
}

// ── Background des tracks ─────────────────────────────────────────────────────
const TRACK_BG=
    'background-color:#f8fafc;'+
    'background-image:linear-gradient(90deg,'+
    'transparent 25%,rgba(0,0,0,.07) 25%,rgba(0,0,0,.07) calc(25% + 1px),transparent calc(25% + 1px),'+
    'transparent 50%,rgba(0,0,0,.07) 50%,rgba(0,0,0,.07) calc(50% + 1px),transparent calc(50% + 1px),'+
    'transparent 75%,rgba(0,0,0,.07) 75%,rgba(0,0,0,.07) calc(75% + 1px),transparent calc(75% + 1px));';

// ── Bar store ─────────────────────────────────────────────────────────────────
let bStore={}, bSeq=0;

function mkBar(run, proj, scen, h, top){
    const cs=Math.max(run.s, viewStart);
    const ce=Math.min(run.e, viewEnd);
    if(ce<=cs) return '';
    const range=viewEnd-viewStart;
    const l=(cs-viewStart)/range*100;
    const w=Math.max((ce-cs)/range*100, 0.15);
    const ok=run.st==='success';
    const bg =ok?'rgba(16,185,129,.82)':'rgba(244,63,94,.85)';
    const brd=ok?'rgba(5,150,105,.4)' :'rgba(220,38,38,.4)';
    const id='tlb'+(bSeq++);
    bStore[id]={proj, scen, s:run.s, e:run.e, d:run.d, st:run.st};
    return `<div id="${id}"
        onmouseenter="tlTT(event,'${id}')" onmouseleave="tlHTT()"
        onmouseover="this.style.filter='brightness(1.2)'"
        onmouseout="this.style.filter=''"
        style="position:absolute;left:${l.toFixed(3)}%;width:${w.toFixed(3)}%;
               top:${top};height:${h};border-radius:4px;
               background:${bg};border:1px solid ${brd};
               cursor:default;box-sizing:border-box;
               transition:filter .1s;"></div>`;
}

// ── Ligne projet ──────────────────────────────────────────────────────────────
function mkProjRow(proj, scenarios){
    let allBars='', hasFailed=false;
    const scenKeys=Object.keys(scenarios);
    const totalRuns=scenKeys.reduce((a,k)=>a+scenarios[k].length, 0);
    scenKeys.forEach(scen=>{
        scenarios[scen].forEach(run=>{
            if(run.st==='failed') hasFailed=true;
            allBars+=mkBar(run, proj, scen, '20px', '14px');
        });
    });

    const bc=hasFailed?'var(--failed)':'var(--success)';
    const isExp=!!expanded[proj];
    const chevCol=isExp?'var(--primary)':'#cbd5e1';
    const chevRot=isExp?'transform:rotate(90deg);':'';

    let html=`
    <div class="tl-proj-row" data-proj="${proj}" onclick="tlToggle(this.dataset.proj)"
        style="display:flex;align-items:stretch;border-top:1px solid var(--border);cursor:pointer;">
        <div style="width:220px;min-width:220px;padding:8px 14px;
                    display:flex;align-items:center;gap:8px;
                    font-size:.78rem;font-weight:700;color:var(--text);
                    border-right:3px solid ${bc};background:white;
                    transition:background .15s;"
             onmouseover="this.style.background='#f8fafc'"
             onmouseout="this.style.background='white'">
            <span class="material-symbols-outlined"
                  style="font-size:14px;color:${chevCol};transition:transform .2s;${chevRot}">
                chevron_right
            </span>
            <span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                  title="${proj}">${proj}</span>
            <span style="font-size:.58rem;font-weight:900;color:#94a3b8;white-space:nowrap;">
                ${scenKeys.length}&nbsp;scen&nbsp;&middot;&nbsp;${totalRuns}&nbsp;runs
            </span>
        </div>
        <div style="flex:1;position:relative;height:48px;${TRACK_BG}">${allBars}</div>
    </div>`;

    if(isExp){
        Object.keys(scenarios).sort().forEach(scen=>{
            const sBars=scenarios[scen].map(r=>mkBar(r, proj, scen, '14px', '9px')).join('');
            const scFailed=scenarios[scen].some(r=>r.st==='failed');
            const scDot=`<span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                background:${scFailed?'var(--failed)':'var(--success)'};flex-shrink:0;margin-right:6px;"></span>`;
            html+=`
            <div style="display:flex;align-items:stretch;border-top:1px solid rgba(0,0,0,.04);background:#f9fafb;">
                <div style="width:220px;min-width:220px;padding:4px 14px 4px 38px;
                            display:flex;align-items:center;
                            font-size:.68rem;color:var(--text-dim);font-weight:600;
                            border-right:1px solid var(--border);">
                    ${scDot}
                    <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                          title="${scen}">${scen}</span>
                </div>
                <div style="flex:1;position:relative;height:32px;${TRACK_BG}">${sBars}</div>
            </div>`;
        });
    }
    return html;
}

// ── Axe des heures (adaptatif selon le zoom) ──────────────────────────────────
function mkAxis(){
    const range=viewEnd-viewStart;
    let step;
    if(range>43200)      step=10800;
    else if(range>21600) step=3600;
    else if(range>7200)  step=1800;
    else if(range>3600)  step=900;
    else if(range>900)   step=300;
    else                 step=60;

    let lbl='';
    const firstTick=Math.ceil(viewStart/step)*step;
    for(let s=firstTick; s<=viewEnd; s+=step){
        const x=((s-viewStart)/range*100).toFixed(2);
        const hh=Math.floor(s/3600);
        const mm=Math.floor((s%3600)/60);
        const timeStr=step<3600
            ?('0'+hh).slice(-2)+':'+('0'+mm).slice(-2)
            :('0'+hh).slice(-2)+'h';
        lbl+=`<span style="position:absolute;left:${x}%;transform:translateX(-50%);
            font-size:.6rem;font-weight:800;color:#94a3b8;
            letter-spacing:.04em;user-select:none;">${timeStr}</span>`;
    }
    return `
    <div style="display:flex;align-items:stretch;border-bottom:2px solid var(--border);">
        <div style="width:220px;min-width:220px;padding:6px 14px;
                    font-size:.6rem;font-weight:800;color:#94a3b8;
                    text-transform:uppercase;letter-spacing:.08em;
                    border-right:1px solid var(--border);
                    background:white;">Project</div>
        <div style="flex:1;position:relative;height:28px;background:white;">${lbl}</div>
    </div>`;
}

// ── Ligne NOW ─────────────────────────────────────────────────────────────────
function mkNowLine(){
    const ns=nowSecs();
    if(ns<viewStart||ns>viewEnd) return '';
    const x=((ns-viewStart)/(viewEnd-viewStart)*100).toFixed(3);
    return `<div id="tl-nl" style="position:absolute;left:${x}%;top:0;bottom:0;
        width:2px;background:var(--primary);opacity:.7;
        pointer-events:none;z-index:5;">
        <div style="position:absolute;top:0;left:-4px;
            width:10px;height:10px;border-radius:50%;
            background:var(--primary);"></div>
        <div style="position:absolute;top:16px;left:5px;
            font-size:.5rem;font-weight:900;
            color:var(--primary);white-space:nowrap;">NOW</div>
    </div>`;
}

// ── Boutons de sélection de jour ──────────────────────────────────────────────
function renderBtns(){
    const c=document.getElementById('tl-day-btns');
    if(!c) return;
    const isZoomed=(viewEnd-viewStart)<86400;
    const resetBtn=isZoomed
        ?`<button class="tl-day-btn" onclick="tlResetZoom()"
            style="background:rgba(79,70,229,.08);color:var(--primary);border:1px solid rgba(79,70,229,.25);margin-left:8px;">
            ↺ Reset zoom
          </button>`
        :'';
    c.innerHTML=DAYS.map(d=>{
        const lbl=isToday(d)?'Today'
            :new Date(d+'T12:00:00').toLocaleDateString('en-GB',{day:'2-digit',month:'short'});
        return `<button class="tl-day-btn${d===cur?' active':''}"
            onclick="tlSelectDay('${d}')">${lbl}</button>`;
    }).join('')+resetBtn;
}

// ── Zoom & Pan ────────────────────────────────────────────────────────────────
function setupZoom(){
    if(zoomSetupDone) return;
    zoomSetupDone=true;
    const wrap=document.getElementById('tl-wrapper');
    if(!wrap) return;

    // Scroll to zoom (centered on cursor position within the track area)
    wrap.addEventListener('wheel', function(e){
        e.preventDefault();
        const rect=wrap.getBoundingClientRect();
        const trackWidth=rect.width-220;
        if(trackWidth<=0) return;
        const mouseX=e.clientX-(rect.left+220);
        const ratio=Math.max(0,Math.min(1,mouseX/trackWidth));
        const focalS=viewStart+ratio*(viewEnd-viewStart);
        const zoomFactor=(e.deltaY||0)>0?1.3:0.77;
        let newRange=Math.max(900,Math.min(86400,(viewEnd-viewStart)*zoomFactor));
        let newStart=focalS-ratio*newRange;
        let newEnd=focalS+(1-ratio)*newRange;
        if(newStart<0){newEnd=Math.min(86400,newEnd-newStart);newStart=0;}
        if(newEnd>86400){newStart=Math.max(0,newStart-(newEnd-86400));newEnd=86400;}
        viewStart=Math.round(newStart);
        viewEnd=Math.round(newEnd);
        render();
    },{passive:false});

    // Drag to pan
    let dragging=false,dragX=0,dragVS=0,dragVE=0,rafId=null;
    wrap.addEventListener('mousedown',function(e){
        const rect=wrap.getBoundingClientRect();
        if(e.clientX-rect.left<220) return;
        dragging=true; dragX=e.clientX; dragVS=viewStart; dragVE=viewEnd;
        wrap.style.cursor='grabbing';
        e.preventDefault();
    });
    document.addEventListener('mousemove',function(e){
        if(!dragging) return;
        if(rafId) return;
        rafId=requestAnimationFrame(function(){
            rafId=null;
            const rect=wrap.getBoundingClientRect();
            const trackWidth=rect.width-220;
            if(trackWidth<=0) return;
            const dsecs=-(e.clientX-dragX)/trackWidth*(dragVE-dragVS);
            let ns=dragVS+dsecs, ne=dragVE+dsecs;
            if(ns<0){ne-=ns;ns=0;}
            if(ne>86400){ns-=(ne-86400);ne=86400;}
            viewStart=Math.round(ns); viewEnd=Math.round(ne);
            render();
        });
    });
    document.addEventListener('mouseup',function(){
        if(!dragging) return;
        dragging=false;
        const w=document.getElementById('tl-wrapper');
        if(w) w.style.cursor=(viewEnd-viewStart)<86400?'grab':'default';
    });
}

// ── Render principal ──────────────────────────────────────────────────────────
function render(){
    bStore={}; bSeq=0;
    renderBtns();
    const wrap=document.getElementById('tl-wrapper');
    if(!wrap) return;

    const dayData=D[cur]||{};
    const projs=Object.keys(dayData).sort();

    if(!projs.length){
        wrap.innerHTML='<div style="padding:48px;text-align:center;color:#94a3b8;'+
            'font-size:.9rem;font-weight:600;">No data for this day</div>';
        return;
    }

    const rows=projs.map(p=>mkProjRow(p, dayData[p])).join('');
    const nl=isToday(cur)?mkNowLine():'';
    const nowWrap=nl
        ?`<div style="position:absolute;top:28px;left:220px;right:0;bottom:0;pointer-events:none;">${nl}</div>`
        :'';

    wrap.innerHTML=`<div style="position:relative;">${mkAxis()}${rows}${nowWrap}</div>`;

    const isZoomed=(viewEnd-viewStart)<86400;
    wrap.style.cursor=isZoomed?'grab':'default';
    setupZoom();
}

// ── Événements ────────────────────────────────────────────────────────────────
window.tlToggle=function(proj){
    if(expanded[proj]) delete expanded[proj];
    else expanded[proj]=true;
    render();
};
window.tlSelectDay=function(day){ cur=day; expanded={}; viewStart=0; viewEnd=86400; render(); };
window.tlResetZoom=function(){ viewStart=0; viewEnd=86400; render(); };

// ── Tooltip ───────────────────────────────────────────────────────────────────
window.tlTT=function(evt, id){
    const d=bStore[id]; if(!d) return;
    const tt=document.getElementById('tl-tt');
    const dot=d.st==='success'?'var(--success)':'var(--failed)';
    const stLbl=d.st==='success'?'Success':'Failed';
    tt.innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:${dot};flex-shrink:0;"></div>
        <span style="font-size:.72rem;font-weight:800;color:var(--text);">${d.proj}</span>
    </div>
    <div style="font-size:.65rem;color:var(--text-dim);margin-bottom:8px;font-weight:600;">${d.scen}</div>
    <div style="font-size:1.2rem;font-weight:900;color:var(--text);letter-spacing:-.03em;">
        ${fmtDur(d.d)}
    </div>
    <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);
                font-size:.65rem;color:var(--text-dim);">
        ${fmtTime(d.s)} &rarr; ${fmtTime(d.e)}
    </div>
    <div style="margin-top:4px;font-size:.65rem;font-weight:700;color:${dot};">${stLbl}</div>`;
    tt.style.opacity='1';
    moveTT(evt);
};
window.tlHTT=function(){ document.getElementById('tl-tt').style.opacity='0'; };

document.addEventListener('mousemove', e=>{
    const tt=document.getElementById('tl-tt');
    if(tt && tt.style.opacity==='1') moveTT(e);
});
function moveTT(e){
    const tt=document.getElementById('tl-tt');
    let x=e.clientX+16, y=e.clientY-10;
    if(x+tt.offsetWidth >window.innerWidth)  x=e.clientX-tt.offsetWidth -16;
    if(y+tt.offsetHeight>window.innerHeight) y=e.clientY-tt.offsetHeight-10;
    tt.style.left=x+'px'; tt.style.top=y+'px';
}

// ── Init ──────────────────────────────────────────────────────────────────────
render();

// Mise à jour de la ligne NOW toutes les 60s (re-render pour recalculer la position)
if(isToday(cur)){
    setInterval(()=>{ if(isToday(cur)) render(); }, 60000);
}
"""
