"use client";
import { useState, useEffect, useRef } from "react";

const MARKETS = {
  LAS: { label:"LAS VEGAS", short:"LAS", metrics:[{value:"93",label:"TOP SCORE",hot:true},{value:"4",label:"FIRE SIGNALS"},{value:"12",label:"BUILDER CONTACTS"},{value:"89031",label:"PRIORITY ZIP"}], targets:[{address:"89031 — RICHMOND AMERICAN",score:"93%",spread:"PRE-ENTRY",hot:true},{address:"89011 — BLUE HERON COMING SOON",score:"88%",spread:"DUAL ENTRY"},{address:"89166 — TRI POINTE + CENTURY",score:"87%",spread:"LAND SQUEEZE"},{address:"89032 — AMARA OSINT ZONE",score:"85%",spread:"DEAD PAPER"}], feed:["[06:20] SCANNING CLARK COUNTY NV GRID...","[06:21] RICHMOND AMERICAN 89031 — COMING SOON CONFIRMED","[06:22] TRIPLE BUILDER PRESSURE DETECTED — 89166","[06:23] FORESTAR BUY BOX MATCH — 89032 CORRIDOR","[06:24] PLAYWRIGHT SCRAPER QUEUED — CLARK COUNTY ASSESSOR","[06:25] MOTIVATION SCORE 93 — FLAGGING FOR PIPELINE"]},
  HTX: { label:"HOUSTON", short:"HTX", metrics:[{value:"82",label:"TOP SCORE",hot:true},{value:"4",label:"FIRE SIGNALS"},{value:"11",label:"BUILDER CONTACTS"},{value:"77441",label:"PRIORITY ZIP"}], targets:[{address:"77441 — POLO RANCH PULLOUT",score:"82%",spread:"ORPHAN LOTS",hot:true},{address:"77441 — FM359 PERIMETER",score:"78%",spread:"AG LAND"},{address:"77493 — FREEMAN RANCH EDGE",score:"71%",spread:"EDGE LOT"},{address:"77449 — RAINTREE INFILL",score:"68%",spread:"INFILL"}], feed:["[06:20] SCANNING FORT BEND + HARRIS COUNTY TX...","[06:21] POLO RANCH BUILDER PULLOUT — CONFIRMED","[06:22] FULSHEAR PERIMETER TRACTS IDENTIFIED","[06:23] M/I HOMES 1000-HOME COMMUNITY — LAND DEMAND UP","[06:24] FORESTAR MATCH — FULSHEAR CORRIDOR","[06:25] HCAD VACANT PARCEL QUERY READY"]},
  DFW: { label:"DFW", short:"DFW", metrics:[{value:"91",label:"TOP SCORE",hot:true},{value:"4",label:"FIRE SIGNALS"},{value:"12",label:"BUILDER CONTACTS"},{value:"75126",label:"PRIORITY ZIP"}], targets:[{address:"75126 — FM548 197-ACRE TRACT",score:"91%",spread:"+197AC",hot:true},{address:"75009 — CELINA PERIMETER",score:"84%",spread:"AG LAND"},{address:"75126 — GOLDEN MEADOW LOTS",score:"76%",spread:"ORPHAN"},{address:"76052 — HASLET GHOST ROADS",score:"73%",spread:"STALLED"}], feed:["[06:20] SCANNING KAUFMAN + COLLIN + TARRANT TX...","[06:21] FM548 FORNEY 197-ACRE TRACT CONFIRMED LISTED","[06:22] CELINA PERIMETER — WINDOW CLOSING FAST","[06:23] FORNEY 75126 RANKED #6 HOTTEST US ZIP","[06:24] FORESTAR + TROPHY SIGNATURE BUY BOX MATCHED","[06:25] GOLDEN MEADOW ORPHAN LOTS — MOTIVATED SELLER"]},
  PHX: { label:"PHOENIX", short:"PHX", metrics:[{value:"88",label:"TOP SCORE",hot:true},{value:"3",label:"FIRE SIGNALS"},{value:"11",label:"BUILDER CONTACTS"},{value:"85396",label:"PRIORITY ZIP"}], targets:[{address:"85396 — BUCKEYE EXPANSION ZONE",score:"88%",spread:"PERIMETER",hot:true},{address:"85142 — ELLIOTT CLOSEOUT SEAM",score:"85%",spread:"CLOSEOUT"},{address:"85388 — SURPRISE GHOST ROADS",score:"79%",spread:"STALLED"}], feed:["[06:20] SCANNING MARICOPA COUNTY AZ GRID...","[06:21] BUCKEYE — DAVID WEEKLEY + TAYLOR MORRISON ACTIVE","[06:22] ELLIOTT CLOSEOUT 85142 — PEAK LEVERAGE WINDOW","[06:23] GHOST ROADS DETECTED — 85388 SURPRISE CORRIDOR","[06:24] FORESTAR MATCH CONFIRMED — 85033 / 85041","[06:25] MARICOPA GIS PARCEL QUERY READY"]},
  FLA: { label:"FLORIDA", short:"FLA", metrics:[{value:"94",label:"TOP SCORE",hot:true},{value:"4",label:"FIRE SIGNALS"},{value:"10",label:"BUILDER CONTACTS"},{value:"33837",label:"PRIORITY ZIP"}], targets:[{address:"33837 — HORSESHOE CREEK 170-LOT SITE",score:"94%",spread:"SHOVEL-READY",hot:true},{address:"33837 — WATERSONG 27-LOT PACKAGE",score:"89%",spread:"BULK LOTS"},{address:"34771 — ST CLOUD 52.5 ACRES",score:"82%",spread:"LARGE TRACT"},{address:"33881 — WINTER HAVEN INFILL",score:"76%",spread:"INFILL"}], feed:["[06:20] SCANNING POLK + OSCEOLA COUNTY FL...","[06:21] HORSESHOE CREEK — 170-LOT APPROVAL CONFIRMED","[06:22] WATERSONG 27-LOT BULK PACKAGE — MOTIVATED SELLER","[06:23] DR HORTON DOMINANT IN 33837 — FORESTAR MATCH","[06:24] LGI HOMES BUY BOX — WINTER HAVEN CONFIRMED","[06:25] POLK COUNTY PA PARCEL QUERY READY"]},
  CLT: { label:"CHARLOTTE", short:"CLT", metrics:[{value:"81",label:"TOP SCORE",hot:true},{value:"3",label:"FIRE SIGNALS"},{value:"10",label:"BUILDER CONTACTS"},{value:"28110",label:"PRIORITY ZIP"}], targets:[{address:"28110 — KOLTER DUAL EXPANSION",score:"81%",spread:"BUILDER PUSH",hot:true},{address:"28078 — HUNTERSVILLE STALE LOT",score:"77%",spread:"STALE LIST"},{address:"28110 — 26-ACRE REDEVELOPMENT",score:"74%",spread:"REZONE"}], feed:["[06:20] SCANNING MECKLENBURG + UNION COUNTY NC...","[06:21] KOLTER HOMES DUAL COMMUNITY — 28110 PRESSURE","[06:22] HUNTERSVILLE 0.88 ACRE STALE LOT — 3 YEARS UNSOLD","[06:23] CENTURY COMMUNITIES ACTIVE IN 3 TARGET ZIPS","[06:24] POLARIS GIS QUERY READY — MECKLENBURG","[06:25] M/I HOMES + MATTAMY BUYER MATCH CONFIRMED"]},
};

const TOP5 = [
  {rank:1,zip:"33837",market:"FLA",score:94,type:"SHOVEL-READY"},
  {rank:2,zip:"89031",market:"LAS",score:93,type:"PRE-ENTRY"},
  {rank:3,zip:"75126",market:"DFW",score:91,type:"197-ACRE TRACT"},
  {rank:4,zip:"85396",market:"PHX",score:88,type:"PERIMETER"},
  {rank:5,zip:"75009",market:"DFW",score:84,type:"AG LAND"},
];

const STYLES = `
  @keyframes fadeIn    { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  @keyframes blink     { 0%,100%{opacity:1} 50%{opacity:0} }
  @keyframes spinCW    { to{transform:rotate(360deg)} }
  @keyframes spinCCW   { to{transform:rotate(-360deg)} }
  @keyframes scanline  { from{transform:translateY(-100%)} to{transform:translateY(100vh)} }
  @keyframes faceScan  { from{top:-100%} to{top:200%} }
  @keyframes gridPulse { 0%,100%{opacity:.22} 50%{opacity:.42} }
  @keyframes pulse     { 0%,100%{opacity:1} 50%{opacity:.28} }
  @keyframes voiceBar  { 0%,100%{transform:scaleY(.15)} 50%{transform:scaleY(1)} }
  @keyframes glitch    { 0%,88%,100%{transform:translate(0)} 90%{transform:translate(-2px,1px)} 92%{transform:translate(2px,-1px)} 94%{transform:translate(-1px,0)} }
  @keyframes breathe   { 0%,100%{opacity:.18} 50%{opacity:.4} }
  * { box-sizing:border-box; margin:0; padding:0; }
  ::-webkit-scrollbar { display:none; }
`;

function Panel({ children, style={}, bright=false }: { children: React.ReactNode; style?: React.CSSProperties; bright?: boolean }) {
  const c = bright ? "rgba(255,255,255,.55)" : "rgba(255,255,255,.2)";
  return (
    <div style={{background:"rgba(255,255,255,.025)",border:`1px solid rgba(255,255,255,${bright ? .18 : .08})`,position:"relative",...style}}>
      {[
        {top:-1,left:-1,borderTop:`2px solid ${c}`,borderLeft:`2px solid ${c}`},
        {top:-1,right:-1,borderTop:`2px solid ${c}`,borderRight:`2px solid ${c}`},
        {bottom:-1,left:-1,borderBottom:`2px solid ${c}`,borderLeft:`2px solid ${c}`},
        {bottom:-1,right:-1,borderBottom:`2px solid ${c}`,borderRight:`2px solid ${c}`},
      ].map((s,i) => <div key={i} style={{position:"absolute",width:10,height:10,...s as React.CSSProperties}}/>)}
      {children}
    </div>
  );
}

function VoiceWave({ active }: { active: boolean }) {
  const N = 36;
  const heights = Array.from({length:N}, (_,i) => Math.abs(Math.sin(i*0.7+1))*20+8);
  return (
    <div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:"2px",height:40,padding:"0 4px"}}>
      {Array.from({length:N}, (_,i) => (
        <div key={i} style={{
          width:3,
          background:`rgba(255,255,255,${active ? 0.5+Math.abs(Math.sin(i*0.5))*0.4 : 0.18})`,
          borderRadius:2,
          flexShrink:0,
          height: active ? `${heights[i]}px` : "3px",
          animation: active ? `voiceBar ${0.35+Math.abs(Math.sin(i*0.9))*0.5}s ease-in-out ${(i*0.05).toFixed(2)}s infinite` : "none",
          transition:"height 0.4s ease, background 0.3s",
        }}/>
      ))}
    </div>
  );
}

function AmaraCore({ pulse, speaking }: { pulse: boolean; speaking: boolean }) {
  return (
    <div style={{position:"relative",width:256,height:256,margin:"0 auto"}}>
      {[0,1,2].map(i => (
        <div key={i} style={{
          position:"absolute", inset:i*14, borderRadius:"50%",
          border:`1px solid rgba(255,255,255,${.14-i*.03})`,
          boxShadow: i===0 && pulse ? "0 0 24px rgba(255,255,255,.06)" : "none",
          animation:`${i%2===0 ? "spinCW" : "spinCCW"} ${32+i*20}s linear infinite`,
        }}/>
      ))}
      <div style={{position:"absolute",inset:8,borderRadius:"50%",border:"1px dashed rgba(255,255,255,.12)",animation:"spinCW 12s linear infinite"}}/>
      {[0,90,180,270].map(a => (
        <div key={a} style={{position:"absolute",top:"50%",left:"50%",width:10,height:1.5,background:"rgba(255,255,255,.65)",transformOrigin:"left center",transform:`rotate(${a}deg) translateX(120px)`}}/>
      ))}
      {[45,135,225,315].map(a => (
        <div key={a} style={{position:"absolute",top:"50%",left:"50%",width:5,height:1,background:"rgba(255,255,255,.3)",transformOrigin:"left center",transform:`rotate(${a}deg) translateX(120px)`}}/>
      ))}
      <div style={{
        position:"absolute", inset:36, borderRadius:"50%",
        border:`1.5px solid rgba(255,255,255,${pulse ? .5 : .22})`,
        overflow:"hidden",
        boxShadow: pulse ? "0 0 40px rgba(255,255,255,.1),inset 0 0 40px rgba(0,0,0,.7)" : "inset 0 0 40px rgba(0,0,0,.7)",
        transition:"box-shadow .6s ease",
        animation:"glitch 9s ease-in-out infinite",
      }}>
        <img
          src="/AMARA-Live-head.png"
          alt="AMARA"
          style={{width:"100%",height:"100%",objectFit:"cover",objectPosition:"center 10%",filter:"grayscale(100%) contrast(1.2) brightness(0.85)",display:"block"}}
        />
        <div style={{position:"absolute",inset:0,borderRadius:"50%",background:"repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.22) 3px,rgba(0,0,0,.22) 4px)",zIndex:2}}/>
        <div style={{position:"absolute",inset:0,borderRadius:"50%",background:"radial-gradient(circle,transparent 35%,rgba(0,0,0,.75) 100%)",zIndex:3}}/>
        <div style={{position:"absolute",left:0,right:0,height:4,background:"linear-gradient(transparent,rgba(255,255,255,.07),transparent)",animation:"faceScan 4s linear infinite",zIndex:4}}/>
      </div>
      <div style={{position:"absolute",bottom:0,left:0,right:0,textAlign:"center",fontSize:9,letterSpacing:".5em",color:"rgba(255,255,255,.55)",fontFamily:"'Courier New',monospace"}}>
        · · · A M A R A · · ·
      </div>
    </div>
  );
}

function IntelFeed({ lines }: { lines: string[] }) {
  const [visible, setVisible] = useState<string[]>([]);
  const [cursor, setCursor] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { setVisible([]); setCursor(0); }, [lines]);
  useEffect(() => {
    if (cursor >= lines.length) return;
    const t = setTimeout(() => { setVisible(v => [...v, lines[cursor]]); setCursor(c => c+1); }, cursor === 0 ? 400 : 750);
    return () => clearTimeout(t);
  }, [cursor, lines]);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [visible]);
  return (
    <div ref={ref} style={{height:128,overflowY:"auto",fontFamily:"'Courier New',monospace",fontSize:11,color:"rgba(255,255,255,.48)",letterSpacing:".1em",lineHeight:2}}>
      {visible.map((line, i) => (
        <div key={i} style={{display:"flex",gap:8,alignItems:"center"}}>
          <span style={{color:"rgba(255,255,255,.27)"}}>▸</span>
          <span>{line}</span>
          {i === visible.length-1 && cursor < lines.length && <span style={{animation:"blink 1s step-end infinite"}}>█</span>}
        </div>
      ))}
    </div>
  );
}

function MetricCard({ value, label, hot, idx }: { value: string; label: string; hot?: boolean; idx: number }) {
  return (
    <div style={{border:`1px solid rgba(255,255,255,${hot ? .18 : .07})`,background:`rgba(255,255,255,${hot ? .06 : .02})`,padding:14,animation:`fadeIn .4s ease both`,animationDelay:`${idx*80}ms`}}>
      <div style={{fontSize:30,fontFamily:"'Courier New',monospace",fontWeight:"bold",color:"#fff",letterSpacing:".05em",lineHeight:1}}>{value}</div>
      <div style={{marginTop:7,fontSize:9,letterSpacing:".25em",color:"rgba(255,255,255,.35)",fontFamily:"'Courier New',monospace"}}>{label}</div>
    </div>
  );
}

function TargetRow({ address, score, spread, hot, idx }: { address: string; score: string; spread: string; hot?: boolean; idx: number }) {
  const [hov, setHov] = useState(false);
  return (
    <div onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{borderBottom:"1px solid rgba(255,255,255,.07)",padding:"11px 14px",cursor:"pointer",background:hov?"rgba(255,255,255,.04)":"transparent",transition:"background .15s",animation:`fadeIn .4s ease both`,animationDelay:`${idx*60+200}ms`}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div style={{fontSize:10,fontFamily:"'Courier New',monospace",letterSpacing:".12em",color:hot?"#fff":"rgba(255,255,255,.62)"}}>{address}</div>
        {hot && <div style={{fontSize:8,color:"#fff",border:"1px solid rgba(255,255,255,.45)",padding:"1px 5px",letterSpacing:".2em",animation:"pulse 2s ease-in-out infinite",whiteSpace:"nowrap"}}>FIRE</div>}
      </div>
      <div style={{marginTop:4,display:"flex",gap:12}}>
        <span style={{fontSize:10,letterSpacing:".1em",color:"rgba(255,255,255,.35)",fontFamily:"'Courier New',monospace"}}>SCORE {score}</span>
        <span style={{fontSize:10,letterSpacing:".1em",color:"rgba(255,255,255,.2)",fontFamily:"'Courier New',monospace"}}>/ {spread}</span>
      </div>
    </div>
  );
}

export default function Page() {
  const [market, setMarket] = useState("LAS");
  const [copied, setCopied] = useState<string | null>(null);
  const [pulse, setPulse] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const data = MARKETS[market as keyof typeof MARKETS];

  useEffect(() => {
    setPulse(true); setSpeaking(true);
    const t1 = setTimeout(() => setPulse(false), 1300);
    const t2 = setTimeout(() => setSpeaking(false), 3500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [market]);

  const copy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => { setCopied(text); setTimeout(() => setCopied(null), 1800); });
  };

  return (
    <>
      <style>{STYLES}</style>
      <main style={{minHeight:"100vh",background:"#000",color:"#fff",fontFamily:"'Courier New',monospace",position:"relative",overflow:"hidden"}}>
        <div style={{position:"fixed",inset:0,backgroundImage:"linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px)",backgroundSize:"40px 40px",pointerEvents:"none",animation:"gridPulse 6s ease-in-out infinite"}}/>
        <div style={{position:"fixed",left:0,right:0,height:2,background:"linear-gradient(transparent,rgba(255,255,255,.05),transparent)",pointerEvents:"none",animation:"scanline 7s linear infinite",zIndex:1}}/>
        <div style={{position:"relative",zIndex:2,maxWidth:1280,margin:"0 auto",padding:"20px"}}>
          {/* Header */}
          <div style={{marginBottom:18,display:"flex",alignItems:"flex-end",justifyContent:"space-between",flexWrap:"wrap",gap:10}}>
            <div>
              <div style={{fontSize:9,letterSpacing:".4em",color:"rgba(255,255,255,.28)",marginBottom:4}}>ACES N 8s GROUP · SCOTT SCHUFFORD · PRINCIPAL</div>
              <h1 style={{fontSize:22,letterSpacing:".25em",color:"#fff",fontWeight:"normal"}}>AMARA OS — COMMAND</h1>
              <div style={{fontSize:9,letterSpacing:".3em",color:"rgba(255,255,255,.28)",marginTop:3}}>DEAD PAPER INTELLIGENCE · {data.label} · EXIT-FIRST PROTOCOL</div>
            </div>
            <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
              {["PropertySubmittal@Forestar.com","acquisitions@lgihomes.com"].map(email => (
                <button key={email} onClick={() => copy(email)} style={{background:"transparent",border:"1px solid rgba(255,255,255,.22)",color:"rgba(255,255,255,.62)",fontSize:9,letterSpacing:".14em",padding:"5px 10px",cursor:"pointer",fontFamily:"inherit",transition:"all .15s"}}>
                  ⭐ {copied === email ? "COPIED" : email}
                </button>
              ))}
            </div>
          </div>

          {/* Top 5 */}
          <Panel style={{marginBottom:16,padding:"12px 16px"}}>
            <div style={{fontSize:9,letterSpacing:".3em",color:"rgba(255,255,255,.3)",marginBottom:10}}>TOP 5 FIRE TARGETS — ALL MARKETS</div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
              {TOP5.map(t => (
                <div key={t.rank} onClick={() => setMarket(t.market)} style={{border:`1px solid rgba(255,255,255,${market === t.market ? .28 : .13})`,padding:"8px 14px",cursor:"pointer",background:market === t.market ? "rgba(255,255,255,.07)" : "transparent",transition:"background .15s",minWidth:112}}>
                  <div style={{fontSize:9,color:"rgba(255,255,255,.35)",letterSpacing:".2em",marginBottom:2}}>#{t.rank}</div>
                  <div style={{fontSize:17,fontWeight:"bold",letterSpacing:".05em"}}>{t.zip}</div>
                  <div style={{fontSize:8,color:"rgba(255,255,255,.35)",letterSpacing:".14em",marginTop:2}}>{t.type}</div>
                  <div style={{fontSize:12,marginTop:3}}>{t.score}</div>
                </div>
              ))}
            </div>
          </Panel>

          {/* Market tabs */}
          <div style={{display:"flex",gap:4,marginBottom:16,flexWrap:"wrap"}}>
            {Object.entries(MARKETS).map(([k, m]) => (
              <button key={k} onClick={() => setMarket(k)} style={{background:market===k?"rgba(255,255,255,.09)":"transparent",border:`1px solid rgba(255,255,255,${market===k ? .3 : .11})`,color:market===k?"#fff":"rgba(255,255,255,.32)",fontSize:10,letterSpacing:".25em",padding:"6px 14px",cursor:"pointer",fontFamily:"inherit",transition:"all .15s"}}>{m.short}</button>
            ))}
          </div>

          {/* Metrics */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10,marginBottom:14}}>
            {data.metrics.map((m, i) => <MetricCard key={m.label} {...m} idx={i}/>)}
          </div>

          {/* 3-col main */}
          <div style={{display:"grid",gridTemplateColumns:"272px 1fr 240px",gap:12,marginBottom:12}}>
            {/* LEFT — AMARA */}
            <Panel bright={pulse} style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"space-between",padding:"18px 14px",gap:12}}>
              <AmaraCore pulse={pulse} speaking={speaking}/>
              <div style={{textAlign:"center",width:"100%"}}>
                <div style={{fontSize:11,letterSpacing:".38em",color:"#fff",marginBottom:4}}>AMARA</div>
                <div style={{fontSize:8,letterSpacing:".28em",color:"rgba(255,255,255,.3)"}}>{pulse ? "PROCESSING..." : "COMMAND CORE ACTIVE"}</div>
              </div>
              <div style={{width:"100%",background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.08)",padding:"8px 4px"}}>
                <div style={{fontSize:8,letterSpacing:".22em",color:"rgba(255,255,255,.28)",textAlign:"center",marginBottom:5}}>
                  {speaking ? "◉ TRANSMITTING" : "○ STANDBY"}
                </div>
                <VoiceWave active={speaking}/>
                <div style={{display:"flex",justifyContent:"space-between",marginTop:5,padding:"0 4px"}}>
                  <span style={{fontSize:7,letterSpacing:".15em",color:"rgba(255,255,255,.2)"}}>20Hz</span>
                  <span style={{fontSize:7,letterSpacing:".15em",color:"rgba(255,255,255,.2)"}}>VOICE SYNTHESIS</span>
                  <span style={{fontSize:7,letterSpacing:".15em",color:"rgba(255,255,255,.2)"}}>20kHz</span>
                </div>
              </div>
              <div style={{display:"flex",gap:5,justifyContent:"center",flexWrap:"wrap"}}>
                {["EXIT-FIRST","NEW MATH","DEAD PAPER"].map(tag => (
                  <span key={tag} style={{fontSize:8,border:"1px solid rgba(255,255,255,.13)",padding:"2px 6px",color:"rgba(255,255,255,.27)",letterSpacing:".1em"}}>{tag}</span>
                ))}
              </div>
            </Panel>

            {/* CENTER — Intel feed */}
            <Panel style={{display:"flex",flexDirection:"column"}}>
              <div style={{borderBottom:"1px solid rgba(255,255,255,.08)",padding:"11px 16px",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <span style={{fontSize:9,letterSpacing:".28em",color:"rgba(255,255,255,.35)"}}>INTEL FEED — {data.label}</span>
                <span style={{fontSize:8,letterSpacing:".2em",color:"rgba(255,255,255,.42)",animation:"pulse 2s ease-in-out infinite"}}>● LIVE</span>
              </div>
              <div style={{padding:"12px 16px",flex:1}}>
                <IntelFeed key={market} lines={data.feed}/>
              </div>
              <div style={{borderTop:"1px solid rgba(255,255,255,.08)",padding:"10px 16px"}}>
                <div style={{fontSize:9,letterSpacing:".25em",color:"rgba(255,255,255,.27)",marginBottom:8}}>STRIKE SEQUENCE</div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"6px 16px"}}>
                  {["LOCK BUYER → FORESTAR","RUN THE NEW MATH","TIE UP CONTRACT","COLLECT SPREAD"].map((s, i) => (
                    <div key={i} style={{display:"flex",gap:8,alignItems:"center"}}>
                      <span style={{fontSize:9,color:"rgba(255,255,255,.28)",width:14,flexShrink:0}}>{i+1}.</span>
                      <span style={{fontSize:10,letterSpacing:".08em",color:"rgba(255,255,255,.48)"}}>{s}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Panel>

            {/* RIGHT — Targets */}
            <Panel>
              <div style={{borderBottom:"1px solid rgba(255,255,255,.08)",padding:"11px 14px",fontSize:9,letterSpacing:".28em",color:"rgba(255,255,255,.35)"}}>PRIORITY TARGETS</div>
              {data.targets.map((t, i) => <TargetRow key={t.address} {...t} idx={i}/>)}
            </Panel>
          </div>

          {/* Footer */}
          <div style={{display:"flex",justifyContent:"space-between",flexWrap:"wrap",gap:6}}>
            <span style={{fontSize:8,letterSpacing:".22em",color:"rgba(255,255,255,.14)"}}>AMARA OS · WE HOLD THE CARDS · ACES N 8s GROUP</span>
            <span style={{fontSize:8,letterSpacing:".18em",color:"rgba(255,255,255,.14)"}}>DEAD PAPER = DISTRESSED ASSETS</span>
          </div>
        </div>
      </main>
    </>
  );
}
