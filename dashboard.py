"""A small read-only Tkinter window: one table, one status line."""
import time
import tkinter as tk
from tkinter import ttk
import config as C


def number(value):
    return '-' if value is None else f'{value:.1f}'


def main():
    root = tk.Tk()
    root.title('Jackfruit — Network Monitor')
    root.geometry('1000x330')
    ttk.Label(root, text='UDP telemetry + SDN monitoring', font=('', 17, 'bold')).pack(pady=15)
    status = ttk.Label(root)
    status.pack(pady=5)
    columns = ('Host', 'Agent', 'TX Mbps', 'RX Mbps', 'Switch Mbps', 'Flow Mbps', 'Util %', 'Alert', 'Quarantine')
    table = ttk.Treeview(root, columns=columns, show='headings', height=4)
    for col in columns:
        table.heading(col, text=col)
        table.column(col, width=105, anchor='center')
    table.pack(fill='x', padx=15, pady=15)
    for host in C.HOSTS:
        table.insert('', 'end', iid=host)
    table.tag_configure('bad', foreground='red')
    ttk.Label(root, text='Warning: 5 Mbps | Confirmed heavy sender: 7 Mbps in all three measurements.\n'
              'h5 is the collector. Close this window without stopping the network.').pack()

    def refresh():
        app, net = C.read('telemetry.json'), C.read('network.json')
        now = time.time()
        app_live = now-app.get('updated', 0) < C.TIMEOUT
        net_live = now-net.get('updated', 0) < C.TIMEOUT
        mode = ('ON' if net.get('mitigation') else 'OFF') if net_live else 'UNKNOWN'
        status.config(text=f'Collector: {"running" if app_live else "offline"}    '
                      f'Controller: {"running" if net_live else "offline"}    Mitigation: {mode}')
        for host in C.HOSTS:
            a = app.get('nodes', {}).get(host, {}) if app_live else {}
            n = net.get('hosts', {}).get(host, {}) if net_live else {}
            up = a.get('status') == 'UP' and now-a.get('seen', 0) < C.TIMEOUT
            agent = ('UP' if up else 'DOWN') if app_live else 'UNKNOWN'
            values = (host, agent, number(a.get('tx') if up else None), number(a.get('rx') if up else None),
                      number(n.get('ingress')), number(n.get('flow')), number(n.get('util')),
                      n.get('level', 'UNKNOWN'), ('YES' if n.get('blocked') else 'NO') if net_live else '?')
            table.item(host, values=values, tags=('bad',) if n.get('blocked') or agent == 'DOWN' else ())
        root.after(1000, refresh)

    refresh()
    root.mainloop()


if __name__ == '__main__':
    main()
