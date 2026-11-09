import numpy as np, re, sys, glob, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

vtk_path = sys.argv[1]
out_png  = sys.argv[2]
title    = sys.argv[3] if len(sys.argv) > 3 else "Canopy 3-View"

txt = open(vtk_path).read()
m = re.search(r'POINTS\s+(\d+)\s+\w+\n', txt); np_ = int(m.group(1))
lines_txt = txt[m.end():].split('\n')
pts = np.array([list(map(float, lines_txt[i].split())) for i in range(np_)])

mc = re.search(r'CELLS\s+(\d+)\s+(\d+)\n', txt)
ncell = int(mc.group(1)); cstart = mc.end(); cend = txt.index('CELL_TYPES', cstart)
raw = np.fromstring(txt[cstart:cend].replace('\n',' '), sep=' ', dtype=np.int64)
cells, i = [], 0
while i < len(raw):
    n = raw[i]; cells.append(raw[i+1:i+1+n]); i += 1+n
cth = txt.index('\n', txt.index('CELL_TYPES'))+1
ct = np.fromstring(' '.join(txt[cth:].split('\n')[:ncell]), sep=' ', dtype=np.int64)

tris  = [cells[k] for k in range(ncell) if ct[k]==5]
lines = [cells[k] for k in range(ncell) if ct[k]==3]
quads = [cells[k] for k in range(ncell) if ct[k]==9]

fig = plt.figure(figsize=(18,6), dpi=150)
views = [('Front view (X-Y)',0,1,'x [m]','y [m]'),
         ('Side view (Z-Y)',2,1,'z [m]','y [m]'),
         ('Top view (X-Z)',0,2,'x [m]','z [m]')]
for vi,(t,a,b,xl,yl) in enumerate(views):
    ax = fig.add_subplot(1,3,vi+1)
    for c in tris+quads:
        ax.add_patch(plt.Polygon(np.column_stack([pts[c,a],pts[c,b]]),
                     facecolor='#4a90d9', edgecolor='#1a3a5c', lw=0.12, alpha=0.85))
    for c in lines:
        ax.plot(pts[c,a], pts[c,b], color='#cc3333', lw=0.5, alpha=0.8)
    ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(t)
    ax.set_aspect('equal'); ax.autoscale_view(); ax.grid(alpha=0.3)
fig.suptitle(title, fontsize=14, fontweight='bold')
fig.tight_layout(rect=[0,0,1,0.94])
fig.savefig(out_png, bbox_inches='tight')
print("saved:", out_png, "tris:", len(tris), "lines:", len(lines))
