import { useEffect, useState } from "react";
import { STATE_LABEL, api } from "../api/client";
type State = "dry" | "wet";
type Rail = { id: number; label: string; length_cm: number };
type Occ = { rail_id: number; label: string; length_cm: number; states: State[]; segments: { ticket_code: string; garment_name: string; garment_state: State; start_cm: number; end_cm: number }[] };
export default function OccupancyPage() {
  const [rails, setRails] = useState<Rail[]>([]);
  const [maps, setMaps] = useState<Occ[]>([]);
  useEffect(() => {
    api<Rail[]>("/rails").then(async rs => {
      setRails(rs);
      const all = await Promise.all(rs.map(r => api<Occ>(`/occupancy/${r.id}`)));
      setMaps(all);
    });
  }, []);
  return (<>
    <h2>占位图（横向尺线）</h2>
    <p className="hint">每杆只允许同一种干湿属性共存；色块：<span className="state-tag state-tag--dry">干衣</span> <span className="state-tag state-tag--wet">湿衣</span> <span className="state-tag state-tag--empty">空杆</span>。</p>
    {maps.map(m => (
      <div className="ruler-wrap" key={m.rail_id}>
        <div className="ruler-label">
          <span>{m.label}
            {" "}
            {m.states.length === 0
              ? <span className="state-tag state-tag--empty">空杆</span>
              : m.states.map(s => <span key={s} className={`state-tag state-tag--${s}`}>{STATE_LABEL[s]}</span>)}
          </span>
          <span className="mono">0 — {m.length_cm} cm</span>
        </div>
        <div className="ruler">
          {m.segments.map((s, i) => (
            <div key={i} className={`seg seg--${s.garment_state}`} style={{ left: `${(s.start_cm / m.length_cm) * 100}%`, width: `${((s.end_cm - s.start_cm) / m.length_cm) * 100}%` }}
              title={`${s.ticket_code} ${STATE_LABEL[s.garment_state]} ${s.start_cm}-${s.end_cm}cm`}>
              {s.garment_name}
            </div>
          ))}
        </div>
      </div>
    ))}
    {!rails.length && <p>暂无挂杆</p>}
  </>);
}
