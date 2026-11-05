# ピアノ風テスト音源：きらきら星（パブリックドメイン）。減衰音・同音連打・左手の和音つき
import json, numpy as np, soundfile as sf
SR=22050; BPM=110; B=60/BPM
mel=[60,60,67,67,69,69,67,65,65,64,64,62,62,60]
dur=[1,1,1,1,1,1,2,1,1,1,1,1,1,2]
def hz(m): return 440*2**((m-69)/12)
def piano(f,d,a):
    t=np.arange(int(d*SR))/SR
    w=sum(h*np.sin(2*np.pi*f*k*t*(1+0.0004*k*k)) for k,h in zip(range(1,8),(1,.6,.35,.25,.15,.1,.05)))
    env=np.minimum(1,t/0.005)*np.exp(-t*3.0)
    return a*w*env
total=sum(dur)*B+2; y=np.zeros(int(total*SR)); pos=0.5; truth=[]
for m,b in zip(mel,dur):
    s=int(pos*SR); seg=piano(hz(m),b*B*1.3,0.5); y[s:s+len(seg)]+=seg[:len(y)-s]
    truth.append({"midi":m,"beats":b}); pos+=b*B
# 左手：2拍ごとに和音
chords=[[48,52,55],[48,52,55],[53,57,60],[48,52,55],[53,57,60],[48,52,55],[43,47,50],[48,52,55]]
for i,ch in enumerate(chords):
    s=int((0.5+i*2*B)*SR)
    for m in ch:
        seg=piano(hz(m),2*B*1.2,0.18); y[s:s+len(seg)]+=seg[:len(y)-s]
y+=np.random.RandomState(0).randn(len(y))*0.003
y/=np.abs(y).max()*1.1
sf.write('test/piano_twinkle.wav',y,SR)
json.dump({"bpm":BPM,"notes":truth},open('test/truth_piano.json','w'))
print('ok')
