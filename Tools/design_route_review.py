from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math
root=Path('/Users/lucas/HKUST_TLE/ISDN5230/canyon_delivery/GliderCanyon_v2')
out=Path('/Users/lucas/HKUST_TLE/ISDN5230/windroute_canyon/RouteReview');out.mkdir(exist_ok=True)
base=Image.open(root/'Renders/topview_v2_clean.png').convert('RGB')
assert base.size==(2048,2048)
W,H=2850,2290; im=Image.new('RGB',(W,H),(16,27,39)); im.paste(base,(30,125));d=ImageDraw.Draw(im,'RGBA')
font='/System/Library/Fonts/STHeiti Medium.ttc'
def F(n): return ImageFont.truetype(font,n,index=0)
def text(xy,s,size=28,color=(238,246,248,255)):d.text(xy,s,font=F(size),fill=color)
text((35,28),'峡谷滑翔 · 新航线概念方案',49);text((37,90),'地形俯视底图：GliderCanyon v2  /  箭头表示建议飞行方向',23,(179,201,208,255))
segments=[
 ([(283,1890),(315,1690),(370,1450),(355,1260),(430,1080),(520,960),(650,850)],(67,218,238,255)),
 ([(650,850),(850,760),(1050,660),(1260,610),(1460,630),(1600,730)],(111,225,141,255)),
 ([(1600,730),(1680,870),(1670,1030),(1600,1190),(1460,1310),(1300,1335)],(255,202,94,255)),
 ([(1300,1335),(1130,1300),(1010,1200),(950,1070),(1000,900),(1130,760),(1300,720),(1480,770)],(255,135,108,255)),
 ([(1480,770),(1650,840),(1750,970),(1800,1140),(1785,1330),(1780,1510)],(204,159,255,255))]
def curve(pts):
    p=[pts[0]]+pts+[pts[-1]];res=[]
    for i in range(1,len(p)-2):
      p0,p1,p2,p3=p[i-1:i+3]
      for k in range(20):
       t=k/20;t2=t*t;t3=t2*t
       res.append(tuple(.5*((2*p1[j])+(-p0[j]+p2[j])*t+(2*p0[j]-5*p1[j]+4*p2[j]-p3[j])*t2+(-p0[j]+3*p1[j]-3*p2[j]+p3[j])*t3) for j in (0,1)))
    return res+[pts[-1]]
curves=[];length=0
for pts,c in segments:
  q=curve(pts);curves.append(q)
  length+=sum(math.dist(a,b) for a,b in zip(q,q[1:]))
  q2=[(x+30,y+125) for x,y in q]
  d.line(q2,fill=(10,23,29,220),width=23,joint='curve');d.line(q2,fill=c,width=11,joint='curve')
  for k in range(18,len(q2)-4,36):
    x,y=q2[k];x0,y0=q2[k-3];a=math.atan2(y-y0,x-x0)
    v=[(x+20*math.cos(a),y+20*math.sin(a)),(x+16*math.cos(a+2.45),y+16*math.sin(a+2.45)),(x+16*math.cos(a-2.45),y+16*math.sin(a-2.45))]
    d.polygon(v,fill=c,outline=(15,30,35,255),width=3)
markers=[(283,1890,'1'),(650,850,'2'),(1600,730,'3'),(1300,1335,'4'),(1480,770,'5'),(1780,1510,'终')]
for x,y,label in markers:
 x+=30;y+=125;d.ellipse((x-30,y-30,x+30,y+30),fill=(10,27,39,245),outline=(255,255,255,255),width=4);bb=d.textbbox((0,0),label,font=F(28));d.text((x-(bb[2]-bb[0])/2,y-23),label,font=F(28),fill='white')
X=2120
text((X,145),'飞行节奏',36)
items=[('1  草原起飞 → 峡谷穿行','低空暖身，宽弯引导左右切换'),('2  出山口 → 草原掠过','视野打开，缓慢爬升后短暂平飞'),('3  主峰东侧 → 山脚','顺山势转弯，自动小幅下降'),('4  山脚 → 西侧高空','分段爬升，中途加入平飞观景'),('5  肩部 → 东南出口','高处掠景后平滑俯冲，飞向终点')]
for i,(title,desc) in enumerate(items):
 y=220+i*185;c=segments[i][1];d.rounded_rectangle((X,y+4,X+20,y+25),5,fill=c);text((X+34,y-3),title,26);text((X+34,y+42),desc,21,(180,199,208,255))
text((X,1200),'垂直节奏 · 概念示意',30)
xx=[X+15,X+105,X+205,X+305,X+390,X+480,X+580,X+650];yy=[1450,1390,1390,1330,1365,1255,1275,1400]
d.line([(X+10,1470),(X+660,1470)],fill=(125,152,161,160),width=2)
d.line(list(zip(xx,yy)),fill=(245,217,131,255),width=6,joint='curve')
for x,y in zip(xx,yy): d.ellipse((x-5,y-5,x+5,y+5),fill=(255,237,176,255))
text((X,1505),'上升 → 平飞 → 小降 → 再上升 → 俯冲',21,(198,215,218,255))
d.rounded_rectangle((X,1600,2800,1945),18,fill=(27,47,59,240))
for j,line in enumerate(['设计原则','• 左右由玩家控制，飞机不自动转弯','• 高度与速度按航段平滑调整','• 圆环沿建议路线约 5–7 秒布置','• 山势、视角与节奏交替变化','• 箭头是意图，非最终飞行轨迹']):
 text((X+24,1620+j*47),line,23 if j else 26)
text((35,2200),'此图为待审核的航线概念，尚未进行地形净空、飞行速度或转弯半径验证。',25,(209,224,229,255))
# Existing render legend shows 200 m / 316 px, so this is an approximate 2-D estimate.
meters=length*200/316
text((35,2245),f'俯视线长粗估约 {meters/1000:.1f} km；以 20 m/s 匀速估算约 {meters/20/60:.1f} 分钟，需以实际地形测量为准。',23,(163,190,200,255))
path=out/'canyon_route_proposal.png';im.save(path,optimize=True)
print(f'{path}  pixels={length:.0f} estimated_m={meters:.0f} seconds={meters/20:.0f}')
