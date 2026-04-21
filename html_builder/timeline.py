# html_builder/timeline.py
# Génère le graphique timeline (Gantt) des exécutions de scénarios par projet.
# Visualise les exécutions simultanées pour détecter les conflits de ressources.

import json
import pandas as pd

from config import COL_PROJECT_ID, COL_RUN_STATUS


def _compute_load_curve(df: pd.DataFrame) -> dict:
    """
    Calcule la courbe de charge sur la journée : nombre de runs actifs simultanément
    pour chaque tranche de 5 minutes (288 points par jour).

    Args:
        df : DataFrame issu de prepare_timeline_data()

    Returns:
        dict {day_str: {"counts": [int×288], "peak": int, "peak_slot": int}}
          - counts    : liste de 288 valeurs (une par tranche de 5 min, 0h→24h)
          - peak      : valeur maximale de counts
          - peak_slot : index du slot au pic (pour affichage de l'heure)
    """
    result = {}
    slots = list(range(0, 86400, 300))  # 288 tranches de 5 min

    for day, day_df in df.groupby("run_day"):
        counts = []
        for slot in slots:
            slot_end = slot + 300
            n = int(((day_df["start_s"] < slot_end) & (day_df["end_s"] > slot)).sum())
            counts.append(n)

        peak      = max(counts) if counts else 0
        peak_slot = counts.index(peak) if peak > 0 else 0

        result[str(day)] = {
            "counts":    counts,
            "peak":      peak,
            "peak_slot": peak_slot,
        }
    return result


def build_timeline_html(df: pd.DataFrame) -> str:
    """
    Génère le composant timeline auto-contenu (HTML + JS inline).

    Chaque jour est rendu avec :
      - Un bloc "Peak Load" au-dessus de la timeline (heure de pic + nb de runs simultanés)
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

    # ── Calcul de la courbe de charge par jour ────────────────────────────────
    peak_data = _compute_load_curve(df)

    # ── Construction du dict de données JS ───────────────────────────────────
    # Structure : {day: {project: {scenario: [{s, e, d, st}]}}}
    days_data: dict = {}
    for row in df.to_dict("records"):
        day  = str(row["run_day"])
        proj = str(row[COL_PROJECT_ID])
        scen = str(row.get("scenario_id", "?"))
        days_data.setdefault(day, {}).setdefault(proj, {}).setdefault(scen, [])

        # avg_duration_s et n_runs_avg peuvent être NaN si pas assez de runs précédents
        avg_raw   = row.get("avg_duration_s")
        n_raw     = row.get("n_runs_avg")
        avg_val   = round(float(avg_raw), 1) if avg_raw is not None and avg_raw == avg_raw else None
        n_val     = int(n_raw) if n_raw is not None and n_raw == n_raw else None

        days_data[day][proj][scen].append({
            "s":   int(round(float(row["start_s"]))),
            "e":   int(round(float(row["end_s"]))),
            "d":   int(round(float(row["run_duration_s"]))),
            "st":  str(row[COL_RUN_STATUS]).lower(),
            "avg": avg_val,   # Durée moyenne des N runs précédents (secondes), ou null
            "n":   n_val,     # Nombre de runs utilisés pour la moyenne
        })

    sorted_days   = sorted(days_data.keys(), reverse=True)
    default_day   = sorted_days[0] if sorted_days else ""
    js_data       = json.dumps(days_data,  ensure_ascii=False, separators=(",", ":"))
    peak_data_j   = json.dumps(peak_data,  ensure_ascii=False, separators=(",", ":"))
    sorted_days_j = json.dumps(sorted_days, ensure_ascii=False)
    default_day_j = json.dumps(default_day)

    script = (
        "<script>\n(function(){\n"
        "const D="    + js_data       + ";\n"
        "const PEAK=" + peak_data_j   + ";\n"
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

        <!-- ── Graphique de charge (Load Chart) ───────────────────────────── -->
        <!-- Aligné avec le Gantt : 220px de label à gauche + zone graphique -->
        <div style="
            background:white;border:1px solid var(--border);border-radius:14px;
            margin-bottom:6px;overflow:hidden;
            box-shadow:0 1px 4px rgba(0,0,0,.04);
        ">
            <!-- En-tête -->
            <div style="display:flex;align-items:center;padding:8px 14px 4px;gap:8px;
                        border-bottom:1px solid var(--border);">
                <span class="material-symbols-outlined"
                      style="font-size:16px;color:var(--primary);">stacked_bar_chart</span>
                <span style="font-size:.6rem;font-weight:900;text-transform:uppercase;
                             letter-spacing:.08em;color:#94a3b8;">Concurrent Runs — Load Chart</span>
                <span id="tl-lc-peak-lbl"
                      style="margin-left:auto;font-size:.6rem;font-weight:800;color:#94a3b8;"></span>
            </div>
            <!-- Corps : label 220px + canvas -->
            <div style="display:flex;align-items:stretch;">
                <div style="width:220px;min-width:220px;padding:6px 14px;
                            font-size:.58rem;font-weight:800;color:#94a3b8;
                            text-transform:uppercase;letter-spacing:.06em;
                            border-right:1px solid var(--border);
                            display:flex;align-items:center;">
                    Concurrent runs
                </div>
                <div style="flex:1;position:relative;height:60px;overflow:hidden;">
                    <canvas id="tl-load-canvas"
                            style="width:100%;height:60px;display:block;"></canvas>
                    <div id="tl-lc-tt" style="
                        position:absolute;top:2px;left:50%;transform:translateX(-50%);
                        font-size:.58rem;font-weight:800;color:var(--primary);
                        pointer-events:none;white-space:nowrap;
                    "></div>
                </div>
            </div>
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

/**
 * durTrend(run)
 * Calcule le ratio durée actuelle / moyenne des N runs précédents.
 * Retourne un objet {ratio, label, color, outline} pour colorer la barre.
 *
 * Seuils (identiques au drill-down) :
 *   ratio > 1.3  → barre orange vif  (plus lent que d'habitude)
 *   ratio < 0.7  → barre vert vif    (plus rapide que d'habitude)
 *   sinon        → couleur normale (vert/rouge selon statut)
 */
function durTrend(run){
    if(run.avg===null||run.avg===undefined||run.avg<=0) return null;
    const ratio=run.d/run.avg;
    if(ratio>1.3) return {ratio, label:'slow',  color:'rgba(251,146,60,.92)', outline:'rgba(234,88,12,.5)'};
    if(ratio<0.7) return {ratio, label:'fast',  color:'rgba(52,211,153,.92)', outline:'rgba(16,185,129,.5)'};
    return null; // Dans la norme → couleur par défaut
}

function mkBar(run, proj, scen, h, top){
    const cs=Math.max(run.s, viewStart);
    const ce=Math.min(run.e, viewEnd);
    if(ce<=cs) return '';
    const range=viewEnd-viewStart;
    const l=(cs-viewStart)/range*100;
    const w=Math.max((ce-cs)/range*100, 0.15);
    const ok=run.st==='success';

    // Couleur de base selon le statut
    let bg =ok?'rgba(16,185,129,.82)':'rgba(244,63,94,.85)';
    let brd=ok?'rgba(5,150,105,.4)' :'rgba(220,38,38,.4)';

    // Override couleur si durée anormale (seulement pour les runs en succès,
    // pour ne pas masquer les échecs)
    const trend=durTrend(run);
    if(trend && ok){
        bg  = trend.color;
        brd = trend.outline;
    }

    const id='tlb'+(bSeq++);
    bStore[id]={proj, scen, s:run.s, e:run.e, d:run.d, st:run.st, avg:run.avg, n:run.n};
    return `<div id="${id}"
        onmouseenter="tlTT(event,'${id}')" onmouseleave="tlHTT()"
        onmouseover="this.style.filter='brightness(1.15)'"
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

// ── Load Chart (graphique de charge) ─────────────────────────────────────────
/**
 * renderLoadChart()
 * Dessine le graphique de charge sur le <canvas id="tl-load-canvas">.
 *
 * Chaque barre représente une tranche de 5 minutes (288 barres sur 24h).
 * La zone visible est alignée avec le Gantt (viewStart/viewEnd).
 * Couleur des barres :
 *   - 0 run    → transparent
 *   - 1-4 runs → bleu primaire léger
 *   - 5-9 runs → orange
 *   - ≥ 10     → rouge
 *
 * Un tooltip flottant affiche le nombre de runs et l'heure au survol.
 */
function renderLoadChart(){
    const canvas=document.getElementById('tl-load-canvas');
    const peakLbl=document.getElementById('tl-lc-peak-lbl');
    if(!canvas) return;

    const p=PEAK[cur];
    if(!p || !p.counts){
        const ctx=canvas.getContext('2d');
        ctx.clearRect(0,0,canvas.width,canvas.height);
        if(peakLbl) peakLbl.textContent='';
        return;
    }

    // Mise à jour du label de pic
    if(peakLbl){
        const ph=Math.floor(p.peak_slot*300/3600);
        const pm=Math.floor((p.peak_slot*300%3600)/60);
        const pTime=('0'+ph).slice(-2)+':'+('0'+pm).slice(-2);
        const peakColor=p.peak>=10?'#f43f5e':p.peak>=5?'#f97316':'#4f46e5';
        peakLbl.innerHTML=`Peak: <span style="color:${peakColor};font-weight:900;">${p.peak} runs</span> at ${pTime}`;
    }

    // Dimensionnement du canvas (DPR pour netteté sur écrans Retina)
    const dpr=window.devicePixelRatio||1;
    const rect=canvas.getBoundingClientRect();
    canvas.width =Math.round(rect.width *dpr);
    canvas.height=Math.round(rect.height*dpr);
    const ctx=canvas.getContext('2d');
    ctx.scale(dpr,dpr);

    const W=rect.width, H=rect.height;
    const counts=p.counts;          // 288 valeurs
    const maxVal=Math.max(p.peak,1);
    const SLOTS=288;
    const SLOT_S=300;                // 5 min en secondes

    // On ne dessine que les slots visibles (alignement avec viewStart/viewEnd)
    const firstSlot=Math.floor(viewStart/SLOT_S);
    const lastSlot =Math.ceil(viewEnd/SLOT_S);
    const range=viewEnd-viewStart;

    ctx.clearRect(0,0,W,H);

    for(let i=firstSlot;i<lastSlot&&i<SLOTS;i++){
        const slotStart=i*SLOT_S;
        const slotEnd  =(i+1)*SLOT_S;
        const x1=((Math.max(slotStart,viewStart)-viewStart)/range)*W;
        const x2=((Math.min(slotEnd,viewEnd)   -viewStart)/range)*W;
        const barW=Math.max(x2-x1,0.5);
        const v=counts[i]||0;
        if(v===0) continue;

        const barH=Math.max((v/maxVal)*(H-4),2);
        const y=H-barH;

        // Couleur selon intensité
        let color;
        if(v>=10)      color='rgba(244,63,94,.80)';   // rouge
        else if(v>=5)  color='rgba(249,115,22,.75)';  // orange
        else           color='rgba(79,70,229,.55)';   // bleu primaire

        ctx.fillStyle=color;
        ctx.beginPath();
        ctx.roundRect(x1+0.5, y, barW-1, barH, [2,2,0,0]);
        ctx.fill();
    }

    // Ligne de base
    ctx.strokeStyle='rgba(0,0,0,.06)';
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(0,H-0.5);
    ctx.lineTo(W,H-0.5);
    ctx.stroke();

    // Tooltip au survol
    canvas.onmousemove=function(e){
        const r=canvas.getBoundingClientRect();
        const mx=e.clientX-r.left;
        const ratio=mx/r.width;
        const secs=viewStart+ratio*(viewEnd-viewStart);
        const slot=Math.floor(secs/SLOT_S);
        if(slot<0||slot>=SLOTS) return;
        const v=counts[slot]||0;
        const h=Math.floor(slot*SLOT_S/3600);
        const m=Math.floor((slot*SLOT_S%3600)/60);
        const timeStr=('0'+h).slice(-2)+':'+('0'+m).slice(-2);
        const ttEl=document.getElementById('tl-lc-tt');
        if(ttEl) ttEl.textContent=v>0?`${v} run${v>1?'s':''} @ ${timeStr}`:'';
    };
    canvas.onmouseleave=function(){
        const ttEl=document.getElementById('tl-lc-tt');
        if(ttEl) ttEl.textContent='';
    };
}

// ── Render principal ──────────────────────────────────────────────────────────
function render(){
    bStore={}; bSeq=0;
    renderBtns();
    renderLoadChart();
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

    // ── Indicateur de tendance durée ──────────────────────────────────────────
    let trendHtml='';
    if(d.avg && d.avg>0){
        const ratio=d.d/d.avg;
        const nLbl=d.n?d.n+' runs':'prev. runs';
        const avgLbl=fmtDur(d.avg);
        if(ratio>1.3){
            const pct=Math.round((ratio-1)*100);
            trendHtml=`<div style="margin-top:6px;padding:4px 8px;border-radius:6px;
                background:rgba(251,146,60,.12);border:1px solid rgba(251,146,60,.3);
                font-size:.62rem;font-weight:800;color:rgb(234,88,12);">
                ⬆ +${pct}% vs avg ${avgLbl} (last ${nLbl})
            </div>`;
        } else if(ratio<0.7){
            const pct=Math.round((1-ratio)*100);
            trendHtml=`<div style="margin-top:6px;padding:4px 8px;border-radius:6px;
                background:rgba(52,211,153,.12);border:1px solid rgba(52,211,153,.3);
                font-size:.62rem;font-weight:800;color:rgb(5,150,105);">
                ⬇ -${pct}% vs avg ${avgLbl} (last ${nLbl})
            </div>`;
        } else {
            const pct=Math.round(Math.abs(ratio-1)*100);
            trendHtml=`<div style="margin-top:6px;font-size:.6rem;color:#94a3b8;font-weight:600;">
                ≈ avg ${avgLbl} (±${pct}%, last ${nLbl})
            </div>`;
        }
    }

    tt.innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:${dot};flex-shrink:0;"></div>
        <span style="font-size:.72rem;font-weight:800;color:var(--text);">${d.proj}</span>
    </div>
    <div style="font-size:.65rem;color:var(--text-dim);margin-bottom:8px;font-weight:600;">${d.scen}</div>
    <div style="font-size:1.2rem;font-weight:900;color:var(--text);letter-spacing:-.03em;">
        ${fmtDur(d.d)}
    </div>
    ${trendHtml}
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
