import { useEffect, useState } from "react";
import { api } from "../api/client";
type Rail = { id: number; label: string; length_cm: number };
type Seg = { ticket_code: string; garment_name: string; dry_state: string | null; start_cm: number; end_cm: number };
type Occ = { rail_id: number; label: string; length_cm: number; rail_dry_state: string | null; segments: Seg[] };

function railStateText(s: string | null, count: number) {
  if (!count) return "空杆";
  return s === "wet" ? "湿衣杆" : "干衣杆";
}
function segClass(s: string | null) {
  return s === "wet" ? "seg seg--wet" : "seg seg--dry";
}
function segText(s: string | null) {
  return s === "wet" ? "湿" : "干";
}

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
    {maps.map(m => (
      <div className="ruler-wrap" key={m.rail_id}>
        <div className="ruler-label">
          <span>{m.label}
            <span className={m.segments.length ? (m.rail_dry_state === "wet" ? "rail-state rail-state--wet" : "rail-state rail-state--dry") : "rail-state rail-state--empty"}>
              {railStateText(m.rail_dry_state, m.segments.length)}
            </span>
          </span>
          <span className="mono">0 — {m.length_cm} cm</span>
        </div>
        <div className="ruler">
          {m.segments.map((s, i) => (
            <div key={i} className={segClass(s.dry_state)} style={{ left: `${(s.start_cm / m.length_cm) * 100}%`, width: `${((s.end_cm - s.start_cm) / m.length_cm) * 100}%` }}
              title={`${s.ticket_code} ${s.start_cm}-${s.end_cm}cm · ${s.dry_state === "wet" ? "湿衣" : "干衣"}`}>
              <span className="seg-state">{segText(s.dry_state)}</span>{s.garment_name}
            </div>
          ))}
        </div>
      </div>
    ))}
    {!rails.length && <p>暂无挂杆</p>}
  </>);
}
