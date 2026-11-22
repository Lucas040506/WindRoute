from pathlib import Path
import numpy as np, wave
from scipy.signal import butter,sosfiltfilt
R=24000; rng=np.random.default_rng(5231); out=Path(__file__).resolve().parents[1]/'Assets/Audio/Integrated'
def save(name,x):
 x=np.clip(x,-.92,.92)
 with wave.open(str(out/name),'wb') as f: f.setnchannels(1);f.setsampwidth(2);f.setframerate(R);f.writeframes((x*32767).astype('<i2').tobytes())
# A periodic filtered-noise texture, with a gentle swell; the FFT construction loops cleanly.
n=R*8; f=np.fft.rfftfreq(n,1/R); phases=rng.uniform(0,2*np.pi,len(f));shape=np.exp(-((f-420)/700)**2)*(1-np.exp(-(f/90)**2)); spectrum=shape*np.exp(1j*phases);spectrum[0]=0;spectrum[-1]=spectrum[-1].real
x=np.fft.irfft(spectrum,n);x=x/(np.std(x)+1e-9);t=np.arange(n)/R
x*=.085*(.86+.09*np.sin(2*np.pi*t/8)+.05*np.sin(4*np.pi*t/8));save('glide_wind.wav',x)
# Air sweep with gradual attack, not a sharp impact.
n=R*2;t=np.arange(n)/R;noise=rng.standard_normal(n);lo=sosfiltfilt(butter(3,[150,3200],btype='bandpass',fs=R,output='sos'),noise)
env=np.exp(-((t-.82)/.39)**2);lo=lo/(np.std(lo)+1e-9)*env*.13;save('wind_sweep.wav',lo)
print('Generated wind loop and sweep')
