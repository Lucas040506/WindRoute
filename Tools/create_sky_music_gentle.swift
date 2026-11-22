import Foundation
import AVFoundation
import AudioToolbox

let rate=44100.0, beat=60.0/112.0, bars=64, bar=4.0*(60.0/112.0)
let duration=Double(bars)*bar
let dest=URL(fileURLWithPath:CommandLine.arguments[1])
let bank=URL(fileURLWithPath:"/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls")
let engine=AVAudioEngine()
let format=AVAudioFormat(standardFormatWithSampleRate:rate,channels:2)!
let programs:[UInt8]=[12,24,45,73,89,115,33] // marimba, nylon guitar, pizzicato, flute, warm pad, woodblock, bass
let volumes:[Float]=[0.24,0.24,0.12,0.17,0.23,0.075,0.11]
let pans:[Float]=[-0.22,0.23,-0.32,0.08,0.0,0.25,0.0]
let reverb=AVAudioUnitReverb()
engine.attach(reverb)
reverb.loadFactoryPreset(.mediumHall)
reverb.wetDryMix=12
engine.connect(engine.mainMixerNode,to:reverb,format:format)
engine.connect(reverb,to:engine.outputNode,format:format)
var instruments:[AVAudioUnitSampler]=[]
for (i,p) in programs.enumerated() {
 let unit=AVAudioUnitSampler();let channel=AVAudioMixerNode();engine.attach(unit);engine.attach(channel);engine.connect(unit,to:channel,format:format);engine.connect(channel,to:engine.mainMixerNode,format:format);channel.pan=pans[i]
 try unit.loadSoundBankInstrument(at:bank,program:p,bankMSB:UInt8(kAUSampler_DefaultMelodicBankMSB),bankLSB:UInt8(kAUSampler_DefaultBankLSB))
 unit.masterGain=20*log10(volumes[i]);instruments.append(unit)
}
struct Event {let frame:Int64;let instrument:Int;let pitch:UInt8;let velocity:UInt8;let on:Bool}
var events=[Event]()
func play(_ instrument:Int,_ pitch:Int,_ start:Double,_ length:Double,_ vel:Int) {
 guard start>=0 && start<duration else{return}
 events.append(Event(frame:Int64(start*rate),instrument:instrument,pitch:UInt8(pitch),velocity:UInt8(vel),on:true))
 events.append(Event(frame:Int64(min(duration,start+length)*rate),instrument:instrument,pitch:UInt8(pitch),velocity:0,on:false))
}
// C major / G major / A minor / F major; a warm repeating foundation with changing lead phrases.
let chords=[[48,52,55,60],[43,47,50,55],[45,48,52,57],[41,45,48,53], [48,52,55,60],[43,47,50,55],[41,45,48,53],[43,47,50,55]]
let lead:[[Int]]=[[76,79,81,79,76,74],[74,79,81,83,79,74],[76,81,84,81,79,76],[77,81,79,76,74,72], [79,84,83,79,76,79],[74,79,83,81,79,74],[72,77,81,79,77,76],[74,79,81,79,76,74]]
for b in 0..<bars {
 let s=Double(b)*bar,c=chords[b%8], section=b/16
 // sustained pad, absent only at the very start
 if b>0 {for n in c[1...3]{play(4,n,s,bar*0.98,55)}}
 play(6,c[0]-12,s,beat*1.8,59);play(6,c[0]-12,s+beat*2,beat*1.7,52)
 // Light alternating guitar arpeggio.
 for k in 0..<8 {let idx=[0,2,1,3,0,2,1,3][k];play(1,c[idx]+12,s+Double(k)*beat/2,beat*0.42, k%2==0 ? 66:54)}
 // Marimba joins from bar 3; no dense continuous melody.
 if b>=2 {for k in [0,2,3,5,7] {let n=c[[0,1,2,3,2,1,3,2][k]]+12;play(0,n,s+Double(k)*beat/2,beat*0.32, k==0 ? 64:56)}}
 // Gentle plucks on offbeats.
 if b>=8 {for k in [1,3,5,7] {play(2,c[(k/2+1)%4]+12,s+Double(k)*beat/2,beat*0.30,47)}}
 // Flute takes periodic breaths, with small variations by section.
 if b%4 != 3 && b>=4 {let notes=lead[(b+section*2)%8];let offsets:[Double]=[0.0,0.75,1.5,2.25,2.75,3.5]
   for k in 0..<notes.count {let length=(k==1 || k==3) ? beat*0.72:beat*0.52;play(3,notes[k],s+offsets[k]*beat,length, k%2==0 ? 57:53)}
 }
 // Light wood percussion, avoiding a heavy dance groove.
 if b>=4 {for k in 0..<8 {play(5,k%4==0 ? 64:76,s+Double(k)*beat/2,0.065,k%4==0 ? 39:24)}}
}
events.sort { a,b in a.frame==b.frame ? (!a.on && b.on) : a.frame<b.frame }
let settings:[String:Any]=[AVFormatIDKey:kAudioFormatLinearPCM,AVSampleRateKey:rate,AVNumberOfChannelsKey:2,AVLinearPCMBitDepthKey:16,AVLinearPCMIsFloatKey:false,AVLinearPCMIsBigEndianKey:false]
let output=try AVAudioFile(forWriting:dest,settings:settings)
try engine.enableManualRenderingMode(.offline,format:format,maximumFrameCount:4096)
try engine.start()
let buffer=AVAudioPCMBuffer(pcmFormat:engine.manualRenderingFormat,frameCapacity:4096)!
var pos:Int64=0, index=0
let end=Int64(duration*rate)
while pos<end {
 while index<events.count && events[index].frame<=pos {let e=events[index];if e.on {instruments[e.instrument].startNote(e.pitch,withVelocity:e.velocity,onChannel:0)} else {instruments[e.instrument].stopNote(e.pitch,onChannel:0)}; index+=1}
 let next=index<events.count ? events[index].frame : end
 let count=AVAudioFrameCount(max(1,min(Int64(4096),min(end-pos,next-pos))))
 let status=try engine.renderOffline(count,to:buffer)
 switch status {case .success: try output.write(from:buffer);pos+=Int64(buffer.frameLength)
 case .insufficientDataFromInputNode,.cannotDoInCurrentContext: continue
 default: fatalError("Offline render failed: \(status.rawValue)")}
}
engine.stop()
print("Created \(duration)s 112 BPM soundtrack: \(dest.path)")
