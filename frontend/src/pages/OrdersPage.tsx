import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
type O = { id: number; ticket_code: string; garment_name: string; length_cm: number; dry_state: string | null; status: string; due_at: string };

const STATE_LABEL: Record<string, string> = { dry: "干衣", wet: "湿衣" };

function stateText(s: string | null) {
  return s === "wet" ? "湿衣" : s === "dry" ? "干衣" : "干衣（历史未标注）";
}
function stateClass(s: string | null) {
  return s === "wet" ? "state-badge state-badge--wet" : "state-badge state-badge--dry";
}

export default function OrdersPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [isolation, setIsolation] = useState(false);
  const reload = () => api<O[]>("/orders").then(setRows);
  useEffect(() => { reload(); }, []);
  function showError(e: unknown) {
    if (e instanceof ApiError) {
      setIsolation(e.code === "isolation_conflict" || e.code === "mixed");
      setErr(e.message);
    } else {
      setIsolation(false);
      setErr(e instanceof Error ? e.message : String(e));
    }
  }
  async function hang(id: number) {
    setMsg(""); setErr(""); setIsolation(false);
    try {
      const o = await api<O>("/hang", { method: "POST", body: JSON.stringify({ order_id: id }) });
      setMsg(`${o.ticket_code} 已上杆（${STATE_LABEL[o.dry_state ?? "dry"]}）`);
      reload();
    } catch (e) { showError(e); }
  }
  async function changeState(o: O, v: string) {
    setMsg(""); setErr(""); setIsolation(false);
    try {
      const updated = await api<O>(`/orders/${o.id}`, {
        method: "PATCH", body: JSON.stringify({ dry_state: v === "unset" ? null : v }),
      });
      setMsg(`${updated.ticket_code} 干湿属性已更新为：${stateText(updated.dry_state)}`);
      reload();
    } catch (e) { showError(e); }
  }
  return (<>
    <h2>工单</h2>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className={isolation ? "err err--isolation" : "err"} role="alert">
      {isolation && <span className="err-tag">干湿隔离</span>}{err}
    </div>}
    <table className="table"><thead><tr><th>票号</th><th>衣物</th><th>衣长</th><th>干湿</th><th>状态</th><th>到期</th><th></th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}><td className="mono">{o.ticket_code}</td><td>{o.garment_name}</td><td className="mono">{o.length_cm}cm</td>
      <td>{(o.status === "ready" || o.status === "overdue")
        ? <select value={o.dry_state ?? "unset"} onChange={e => changeState(o, e.target.value)}
            title="维护干湿属性；同杆只允许一种属性">
            <option value="dry">干衣</option>
            <option value="wet">湿衣</option>
            <option value="unset">未标注（按干衣）</option>
          </select>
        : <span className={stateClass(o.dry_state)}>{stateText(o.dry_state)}</span>}</td>
      <td>{o.status}</td>
      <td className="mono">{new Date(o.due_at).toLocaleString()}</td>
      <td>{(o.status === "ready" || o.status === "overdue") && <button onClick={() => hang(o.id)}>上杆</button>}</td>
    </tr>)}</tbody></table>
  </>);
}
