import { useEffect, useState } from "react";
import { ApiError, STATE_LABEL, api } from "../api/client";
type O = { id: number; ticket_code: string; garment_name: string; length_cm: number; garment_state: "dry" | "wet"; status: string; due_at: string };
export default function OrdersPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const [isolation, setIsolation] = useState(false);
  const reload = () => api<O[]>("/orders").then(setRows);
  useEffect(() => { reload(); }, []);
  function clearNotice() { setMsg(""); setErr(""); setIsolation(false); }
  async function hang(id: number) {
    clearNotice();
    try {
      const o = await api<O>("/hang", { method: "POST", body: JSON.stringify({ order_id: id }) });
      setMsg(`${o.ticket_code} 已上杆（${STATE_LABEL[o.garment_state]}）`);
      reload();
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message);
        setIsolation(e.isIsolationConflict);
      } else setErr(String(e));
    }
  }
  async function setState(id: number, v: "dry" | "wet") {
    clearNotice();
    try {
      await api(`/orders/${id}`, { method: "PATCH", body: JSON.stringify({ garment_state: v }) });
      reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>工单</h2>
    <p className="hint">湿衣与干衣不得同杆：上杆时若杆上存在相反属性将被干湿隔离拦截（即使空隙足够），系统会改扫其它杆。</p>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className={isolation ? "err err--isolate" : "err"}>{isolation && <span className="err-badge">隔离冲突</span>}{err}</div>}
    <table className="table"><thead><tr><th>票号</th><th>衣物</th><th>衣长</th><th>干湿</th><th>状态</th><th>到期</th><th></th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}><td className="mono">{o.ticket_code}</td><td>{o.garment_name}</td><td className="mono">{o.length_cm}cm</td>
      <td>{(o.status === "ready" || o.status === "overdue")
        ? <select value={o.garment_state} onChange={e => setState(o.id, e.target.value as "dry" | "wet")} title="维护干湿属性">
            <option value="dry">干衣</option><option value="wet">湿衣</option>
          </select>
        : <span className={`state-tag state-tag--${o.garment_state}`}>{STATE_LABEL[o.garment_state]}</span>}</td>
      <td>{o.status}</td>
      <td className="mono">{new Date(o.due_at).toLocaleString()}</td>
      <td>{(o.status === "ready" || o.status === "overdue") && <button onClick={() => hang(o.id)}>上杆</button>}</td>
    </tr>)}</tbody></table>
  </>);
}
