#!/usr/bin/env python3
import json, re, calendar
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Polygon, Patch
from matplotlib.lines import Line2D
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
VIS=ROOT/'Module_02'/'visualization'
raw=(VIS/'data.js').read_text()
data=json.loads(raw.removeprefix('window.MAP_SAMPLE = ').strip().removesuffix(';'))
records=data['records']
ref=(ROOT/'module_03'/'2dot_map.html').read_text()
m=re.search(r'var RECORDS = (\[.*?\]), FILTERS = ',ref,re.S)
map_records=json.loads(m.group(1))

COLORS={
 'Compute / Model Behavior':'#4C72B0','Data':'#DD8452','Energy / Land':'#C44E52',
 'Labor':'#55A868','Deployment Context / Weapons':'#8172B3'}
ORDER=list(COLORS)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':11,'axes.labelsize':9,
                     'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})

def save(fig,name):
    fig.savefig(HERE/f'{name}.png',dpi=180,bbox_inches='tight',facecolor='white')
    fig.savefig(HERE/f'{name}.pdf',bbox_inches='tight',facecolor='white')
    plt.close(fig)

def branch_of(r): return (r.get('b') or ['Unknown'])[0]

# 1. Subcategory distribution
sub=Counter(h for r in records for h in r.get('h',[]))
labels=sorted(sub,key=lambda s:tuple(int(x) for x in s.split()[0].split('.')))
def short(s):
    code,*rest=s.split()
    return f"{code}  {' '.join(rest)}"
fig,ax=plt.subplots(figsize=(9.3,7.2))
y=list(range(len(labels)))
barcols=[]
for label in labels:
    major=label.strip()[0]
    barcols.append(COLORS[ORDER[int(major)-1]])
ax.barh(y,[sub[x] for x in labels],color=barcols,height=.68)
ax.set_yticks(y,labels=[short(x) for x in labels]); ax.invert_yaxis()
ax.set_xlabel('Mapped reports assigned to subcategory')
ax.set_title('Distribution across the 22 AI harm subcategories',loc='left',fontweight='bold',pad=12)
ax.grid(axis='x',color='#E5E7EB',lw=.7); ax.set_axisbelow(True)
for yi,label in zip(y,labels): ax.text(sub[label]+7,yi,f'{sub[label]:,}',va='center',fontsize=8)
for split in [7.5,10.5,13.5,17.5]: ax.axhline(split,color='#CBD5E1',lw=.8)
ax.legend(handles=[Patch(color=COLORS[k],label=k) for k in ORDER],loc='lower right',frameon=False,fontsize=8)
fig.text(.01,.005,'Counts are non-exclusive because a report may receive multiple classifications.',fontsize=8,color='#475569')
fig.tight_layout(rect=(0,.025,1,1)); save(fig,'subcategory_distribution_preview')

# 2. Temporal analysis: monthly reporting only
months=[]
cur=date(2021,1,1)
while cur<=date(2026,7,1):
    months.append(cur)
    cur=date(cur.year+(cur.month==12),1 if cur.month==12 else cur.month+1,1)
month_counts={b:Counter() for b in ORDER}
for r in records:
    ds=r.get('d','')
    if not re.match(r'^20\d\d-\d\d',ds): continue
    d=date(int(ds[:4]),int(ds[5:7]),1)
    for b in r.get('b',[]):
        if b in COLORS: month_counts[b][d]+=1
fig,axes=plt.subplots(5,1,figsize=(11,8.4),sharex=True)
for i,(ax,b) in enumerate(zip(axes,ORDER)):
    vals=[month_counts[b][d] for d in months]
    roll=[sum(vals[max(0,j-2):j+1])/len(vals[max(0,j-2):j+1]) for j in range(len(vals))]
    ax.plot(months,vals,color=COLORS[b],alpha=.28,lw=1.0)
    ax.plot(months,roll,color=COLORS[b],lw=2.2)
    ax.fill_between(months,roll,color=COLORS[b],alpha=.07)
    ax.text(.008,.79,b,transform=ax.transAxes,color=COLORS[b],fontweight='bold',fontsize=9)
    ax.grid(axis='y',color='#E5E7EB',lw=.65); ax.set_xlim(months[0],months[-1])
    ax.set_ylabel('Reports',fontsize=8)
    ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
axes[-1].set_xlabel('Source publication month')
fig.suptitle('Temporal patterns in documented AI harm reporting',x=.07,y=.985,ha='left',fontweight='bold',fontsize=14)
fig.legend(handles=[
    Line2D([0],[0],color='#64748B',alpha=.35,lw=1.2,label='Monthly count'),
    Line2D([0],[0],color='#334155',lw=2.2,label='Three-month rolling average')
],loc='upper center',bbox_to_anchor=(.66,.972),ncol=2,frameon=False,fontsize=9)
fig.text(.07,.018,'Dates are primarily source-publication dates. The 2026 interval ends in July; counts describe documentation, not harm incidence.',fontsize=8,color='#475569')
fig.subplots_adjust(top=.91,bottom=.09,left=.07,right=.99,hspace=.24)
save(fig,'temporal_analysis_preview')

# 3. Geographic distribution
fig=plt.figure(figsize=(13,6.7)); gs=fig.add_gridspec(1,2,width_ratios=[2.15,1],wspace=.08)
ax=fig.add_subplot(gs[0,0]); ax.set_facecolor('#F8FAFC')
features=data['countries']['features']
for f in features:
    geom=f.get('geometry') or {}; coords=geom.get('coordinates',[])
    polys=[coords] if geom.get('type')=='Polygon' else coords if geom.get('type')=='MultiPolygon' else []
    for poly in polys:
        if not poly: continue
        ring=poly[0]
        ax.add_patch(Polygon(ring,closed=True,facecolor='#E2E8F0',edgecolor='white',lw=.25,zorder=1))
for r in map_records:
    b=branch_of(r); ax.scatter(r['x'],r['y'],s=7,color=COLORS.get(b,'#64748B'),alpha=.8,edgecolor='white',linewidth=.15,zorder=2)
ax.set_xlim(-180,180); ax.set_ylim(-60,85); ax.set_aspect('equal',adjustable='box'); ax.axis('off')
ax.set_title('(a) Country-level placement of mapped reports',loc='left',fontweight='bold')
ax2=fig.add_subplot(gs[0,1]); cc=Counter(r['k'] for r in records); top=cc.most_common(15)[::-1]
ax2.barh(range(len(top)),[v for _,v in top],color='#334155',height=.65)
ax2.set_yticks(range(len(top)),[k.replace('United States of America','United States') for k,_ in top],fontsize=8)
ax2.set_xscale('log'); ax2.set_xlabel('Mapped reports (log scale)'); ax2.grid(axis='x',color='#E5E7EB',lw=.7); ax2.set_axisbelow(True)
for i,(_,v) in enumerate(top): ax2.text(v*1.08,i,f'{v:,}',va='center',fontsize=8)
ax2.set_title('(b) Fifteen most represented countries',loc='left',fontweight='bold')
fig.suptitle('Geographic coverage and concentration',x=.03,ha='left',fontweight='bold',fontsize=14)
fig.legend(handles=[Patch(color=COLORS[k],label=k) for k in ORDER],loc='lower left',bbox_to_anchor=(.025,.01),ncol=5,frameon=False,fontsize=8)
fig.text(.03,.005,'Positions separate reports within their associated country; they are not verified incident coordinates.',fontsize=8,color='#475569')
fig.subplots_adjust(top=.9,bottom=.12,left=.03,right=.98); save(fig,'geographic_distribution_preview')

# Contact sheet
items=[('A  SUBCATEGORY DISTRIBUTION','subcategory_distribution_preview.png'),
       ('B  INTERFACE OVERVIEW WITH SELECTED REPORT','interface_selected_report_composite.png'),
       ('C  TEMPORAL PATTERNS','temporal_analysis_preview.png')]
thumbs=[]
for title,file in items:
    im=Image.open(HERE/file).convert('RGB'); im.thumbnail((1400,760)); thumbs.append((title,im.copy()))
W=1500; margin=45; title_h=55; gap=42
H=margin+sum(title_h+im.height+gap for _,im in thumbs)
sheet=Image.new('RGB',(W,H),'white'); draw=ImageDraw.Draw(sheet)
try: font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',28)
except: font=ImageFont.load_default()
y=margin
for title,im in thumbs:
    draw.text((margin,y),title,fill='#111827',font=font); y+=title_h
    x=(W-im.width)//2; sheet.paste(im,(x,y)); y+=im.height+gap
sheet.save(HERE/'appendix_figure_overview.png',quality=95)
print('Generated previews in',HERE)
