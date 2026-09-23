import { useEffect, useState } from "react";
import { api } from "../api/client";
type O = { id: number; ticket_code: string; garment_name: string; due_at: string; status: string; dry_state: string | null };
function stateText(s: string | null) { return s === "wet" ? "湿衣" : s === "dry" ? "干衣" : "干衣(未标注)"; }
function stateClass(s: string | null) { return s === "wet" ? "state-badge state-badge--wet" : "state-badge state-badge--dry"; }
export default function OverduePage() {
  const [rows, setRows] = useState<O[]>([]);
  const [msg, setMsg] = useState("");
  const reload = () => api<O[]>("/overdue").then(setRows);
  useEffect(() => { reload(); }, []);
  async function scan() {
    const marked = await api<O[]>("/overdue/scan", { method: "POST", body: "{}" });
    setMsg(`扫描完成，新标记 ${marked.length} 单`);
    reload();
  }
  return (<>
    <h2>逾期</h2>
    <div className="toolbar"><button onClick={scan}>扫描逾期</button>{msg && <span className="ok">{msg}</span>}</div>
    <table className="table"><thead><tr><th>票号</th><th>衣物</th><th>干湿</th><th>到期</th><th>状态</th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}><td className="mono">{o.ticket_code}</td><td>{o.garment_name}</td>
      <td><span className={stateClass(o.dry_state)}>{stateText(o.dry_state)}</span></td>
      <td className="mono">{new Date(o.due_at).toLocaleString()}</td><td>{o.status}</td></tr>)}
      {!rows.length && <tr><td colSpan={5}>暂无逾期</td></tr>}
    </tbody></table>
  </>);
}
