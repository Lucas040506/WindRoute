"""Generate original loopable wind and a gentle ring chime."""
import math, random, struct, wave
from pathlib import Path
RATE=24000
OUT=Path(__file__).resolve().parents[1]/'Assets'/'Audio'
OUT.mkdir(parents=True,exist_ok=True)
def save(name, values):
    with wave.open(str(OUT/name),'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(RATE)
        f.writeframes(b''.join(struct.pack('<h',round(max(-1,min(1,x))*32767)) for x in values))
rng=random.Random(5230)
# Integer-period partials make the ends of the wind texture meet at the loop boundary.
N=RATE*4
partials=[(rng.randrange(100,4800),rng.random()*math.tau,rng.uniform(.15,1)) for _ in range(70)]
values=[]
for i in range(N):
    t=i/N
    value=sum(a*math.sin(math.tau*k*t+p)/(1+k/1500) for k,p,a in partials)
    envelope=.7+.22*math.sin(math.tau*t+.4)+.08*math.sin(2*math.tau*t)
    values.append(value*envelope*.012)
save('wind_loop.wav',values)
values=[]
for i in range(int(RATE*.85)):
    t=i/RATE
    env=(1-math.exp(-t*80))*math.exp(-t*4.3)
    v=(math.sin(math.tau*660*t)+.48*math.sin(math.tau*990*t)+.22*math.sin(math.tau*1320*t))
    values.append(.22*env*v)
save('ring_chime.wav',values)
print('Created original audio:', *(str(p) for p in OUT.glob('*.wav')))
