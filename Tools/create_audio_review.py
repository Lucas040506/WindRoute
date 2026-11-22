"""Original procedural audio sketches for review; does not modify game assets."""
from pathlib import Path
import math, wave
import numpy as np
R=24000
OUT=Path(__file__).resolve().parents[1]/'AudioReview'; OUT.mkdir(exist_ok=True)
rng=np.random.default_rng(5230)
def write(name,x):
    x=np.asarray(x); x=np.clip(x,-.98,.98)
    with wave.open(str(OUT/name),'wb') as w:
        w.setnchannels(1 if x.ndim==1 else x.shape[1]); w.setsampwidth(2); w.setframerate(R); w.writeframes((x*32767).astype('<i2').tobytes())
def note(m): return 440*2**((m-69)/12)
def bell(m,d=1.7):
    t=np.arange(int(R*d))/R; f=note(m)
    return (1-np.exp(-40*t))*(np.sin(2*np.pi*f*t)*np.exp(-2.2*t)+.23*np.sin(2*np.pi*f*2.01*t)*np.exp(-4*t)+.1*np.sin(2*np.pi*f*3.98*t)*np.exp(-6*t))
def add(buf, v, start, gain=1, pan=0):
    n=int(start*R); n=max(0,n); length=min(len(v),len(buf)-n)
    if length<=0:return
    if buf.ndim==2:
        buf[n:n+length,0]+=v[:length]*gain*math.sqrt((1-pan)/2);buf[n:n+length,1]+=v[:length]*gain*math.sqrt((1+pan)/2)
    else: buf[n:n+length]+=v[:length]*gain
# 48 bars at 84 bpm: ~137 seconds, four harmonic sections.
bpm=84; beat=60/bpm; bar=4*beat; duration=48*bar
music=np.zeros((round(R*duration),2),dtype=np.float32)
chords=[[48,55,60,64],[45,52,57,60],[41,48,53,57],[43,50,55,59], [48,55,60,64],[43,50,55,59],[45,52,57,60],[41,48,53,57]]
for b in range(48):
    chord=chords[b%len(chords)]; start=b*bar
    # Slow, overlapping soft synth tones.
    t=np.arange(round((bar+.8)*R))/R
    env=np.minimum(1,t/.7)*np.minimum(1,np.maximum(0,(bar+.8-t)/1.4))
    for j,m in enumerate(chord[1:]):
        f=note(m); tone=(np.sin(2*np.pi*f*t)+.17*np.sin(2*np.pi*f*2*t)) * env
        add(music,tone,start,.035,[-.55,.25,.55][j])
    # Repeated broken-chord accompaniment.
    pattern=[0,2,1,3,0,2,1,3]
    for k,ix in enumerate(pattern):
        m=chord[ix]+(12 if ix==0 else 0)
        add(music,bell(m,1.35),start+k*beat/2,.052, -.4 if k%2==0 else .4)
    # Sparse melodic figures with breath and small changes.
    if b%4 in (0,2):
        melody=([72,76,79,76] if b%8<4 else [69,72,76,74]) if b%4==0 else ([67,72,74,76] if b%8<4 else [72,69,67,64])
        for k,m in enumerate(melody):
            add(music,bell(m,2),start+(k*.75+.25)*beat,.065,(-.22+.14*k))
# Short feedback cues.
t=np.arange(int(.9*R))/R
noise=rng.normal(size=len(t)); smooth=np.convolve(noise,np.ones(45)/45,'same')
sweep=smooth*np.exp(-((t-.24)/.13)**2)*.09
approach=np.convolve(rng.normal(size=round(R*1.0)),np.ones(55)/55,'same')
at=np.arange(len(approach))/R
approach=approach*np.sin(np.pi*at)**2*.11
write('02_approach.wav',approach)
ring=np.zeros(round(R*1.5));add(ring,sweep,0,1);add(ring,bell(79,1.4),.14,.25);add(ring,bell(86,1.1),.23,.12)
write('03_ring_pass.wav',ring)
miss=np.zeros(round(R*1.5));t=np.arange(round(R*1.3))/R
phase=2*np.pi*(310*t-65*t*t);miss[:len(t)]=.18*np.sin(phase)*(1-np.exp(-25*t))*np.exp(-3.5*t)
write('04_ring_missed.wav',miss)
recover=np.zeros(round(R*2));add(recover,bell(72,1.7),0,.14);add(recover,bell(76,1.5),.18,.13);add(recover,bell(79,1.3),.37,.16)
write('05_power_restored.wav',recover)
# Fade ends for pleasant review; the full track is a composition sketch, not a seamless loop.
n=round(R*2); music[:n]*=np.linspace(0,1,n)[:,None]; music[-n:]*=np.linspace(1,0,n)[:,None]
peak=np.max(np.abs(music)); music*=.75/max(1,peak/.75)
write('01_canyon_journey_music.wav',music)
print('Created',duration,'seconds at',OUT)
