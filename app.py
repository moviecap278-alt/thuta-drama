import streamlit as st
import os
import tempfile
import asyncio
import subprocess
import edge_tts
from deep_translator import GoogleTranslator
from faster_whisper import WhisperModel
import soundfile as sf
import numpy as np
import gdown

st.set_page_config(page_title="THUTA — 1080p Pro Auto-Dubbing", page_icon="🎬", layout="wide")

st.title("🎬 THUTA — 1080p Auto-Dubbing Studio (Up to 5GB / 10 Mins)")
st.caption("နိုင်ငံခြားဗီဒီယို တင်လိုက်ရုံဖြင့် မူရင်း 1080p အရည်အသွေးမပျက်ဘဲ မြန်မာစကားပြော အလိုအလျောက် ထုတ်ပေးသည့်စနစ်")

with st.sidebar:
    st.header("⚙️ အသံနှင့် စနစ် ပြင်ဆင်ရန်")
    voice_choice = st.selectbox(
        "🎙️ မြန်မာ AI အသံ",
        options=[
            ("သီဟ - အမျိုးသားအသံ (Recap/Drama)", "my-MM-ThihaNeural"),
            ("နီလာ - အမျိုးသမီးအသံ (Drama)", "my-MM-NilarNeural")
        ],
        format_func=lambda x: x[0]
    )
    selected_voice = voice_choice[1]
    speech_rate = st.slider("⚡ စကားပြောနှုန်း (Speed)", min_value=-20, max_value=50, value=15, step=5, format="+%d%%")
    bg_volume = st.slider("🔉 မူရင်းဗီဒီယို အသံတိုးမည့်ပမာဏ (BG Volume)", min_value=0.0, max_value=0.5, value=0.08, step=0.02)

@st.cache_resource
def get_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

async def make_tts(text, voice, rate, out_file):
    rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
    comm = edge_tts.Communicate(text, voice, rate=rate_str)
    await comm.save(out_file)

upload_mode = st.radio("📥 ဗီဒီယို ထည့်သွင်းမည့်ပုံစံ ရွေးပါ", ["ဖုန်း/စက်ထဲမှ တိုက်ရိုက်တင်မည် (Up to 5GB)", "Google Drive Link ဖြင့် တင်မည် (ဖိုင်အကြီးများအတွက် အကောင်းဆုံး)"])

video_ready = False
temp_dir = tempfile.mkdtemp()
input_video_path = os.path.join(temp_dir, "input_1080p.mp4")

if upload_mode == "ဖုန်း/စက်ထဲမှ တိုက်ရိုက်တင်မည် (Up to 5GB)":
    up_file = st.file_uploader("ဗီဒီယို ရွေးချယ်ပါ (MP4, MKV, MOV - 1080p, Max 5GB)", type=["mp4", "mkv", "mov"])
    if up_file is not None:
        with open(input_video_path, "wb") as f:
            f.write(up_file.getbuffer())
        video_ready = True
else:
    gdrive_url = st.text_input("🔗 Google Drive Video Link (Anyone with link ဖွင့်ထားသော လင့်ခ်) ထည့်ပါ")
    if gdrive_url:
        video_ready = True

if video_ready:
    if st.button("🚀 မြန်မာစကားပြော ဗီဒီယို စတင်ထုတ်လုပ်မည် (1080p Full HD)", type="primary", use_container_width=True):
        progress = st.progress(0, text="စတင်နေပါသည်...")
        try:
            if upload_mode.startswith("Google Drive"):
                progress.progress(10, text="Google Drive မှ ဗီဒီယို ဆွဲယူနေပါသည်...")
                gdown.download(gdrive_url, input_video_path, quiet=False, fuzzy=True)

            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_video_path],
                capture_output=True, text=True
            )
            total_duration_sec = float(probe.stdout.strip())

            progress.progress(25, text="အဆင့် ၁/၄ - နိုင်ငံခြားစကားပြောများကို အချိန်ကိုက် ဖမ်းယူနေပါသည်...")
            model = get_whisper()
            segments, _ = model.transcribe(input_video_path, beam_size=5)
            seg_list = list(segments)

            progress.progress(50, text="အဆင့် ၂/၄ - မြန်မာဘာသာပြန်ပြီး အချိန်ကိုက် AI အသံသွင်းနေပါသည်...")
            translator = GoogleTranslator(source='auto', target='my')
            
            sample_rate = 22050
            total_samples = int(total_duration_sec * sample_rate)
            master_audio = np.zeros(total_samples, dtype=np.float32)

            log_box = st.expander("📜 ဘာသာပြန် စာသားများ ကြည့်ရန်", expanded=False)
            for idx, seg in enumerate(seg_list):
                orig_txt = seg.text.strip()
                if not orig_txt:
                    continue
                my_txt = translator.translate(orig_txt)
                log_box.write(f"⏱️ `{seg.start:.1f}s - {seg.end:.1f}s`: {my_txt}")
                
                seg_tts_path = os.path.join(temp_dir, f"seg_{idx}.mp3")
                asyncio.run(make_tts(my_txt, selected_voice, speech_rate, seg_tts_path))
                
                if os.path.exists(seg_tts_path):
                    seg_wav_path = os.path.join(temp_dir, f"seg_{idx}.wav")
                    subprocess.run(["ffmpeg", "-y", "-i", seg_tts_path, "-ar", str(sample_rate), "-ac", "1", seg_wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    if os.path.exists(seg_wav_path):
                        data, fs = sf.read(seg_wav_path)
                        start_sample = int(seg.start * sample_rate)
                        end_sample = start_sample + len(data)
                        if end_sample > len(master_audio):
                            master_audio = np.pad(master_audio, (0, end_sample - len(master_audio)))
                        master_audio[start_sample:end_sample] += data

            dub_wav_path = os.path.join(temp_dir, "master_dub.wav")
            sf.write(dub_wav_path, master_audio, sample_rate)

            progress.progress(85, text="အဆင့် ၃/၄ - မူရင်း 1080p ဗီဒီယိုနှင့် မြန်မာအသံ ပေါင်းစပ်နေပါသည်...")
            output_path = os.path.join(temp_dir, "THUTA_1080p_Burmese_Dubbed.mp4")
            
            subprocess.run([
                "ffmpeg", "-y",
                "-i", input_video_path,
                "-i", dub_wav_path,
                "-filter_complex", f"[0:a]volume={bg_volume}[bg];[1:a]volume=1.5[dub];[bg][dub]amix=inputs=2:duration=first[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ], check=True)

            progress.progress(100, text="✅ အောင်မြင်စွာ ပြီးဆုံးပါပြီ!")
            st.success("🎉 1080p မြန်မာစကားပြော ဗီဒီယို ထုတ်လုပ်ပြီးပါပြီ!")
            st.video(output_path)

            with open(output_path, "rb") as f:
                st.download_button(
                    "⬇️ 1080p မြန်မာစကားပြော ဗီဒီယို ဒေါင်းလုဒ်ဆွဲရန် (Download MP4)",
                    data=f,
                    file_name="THUTA_1080p_Burmese.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Error: {str(e)}")
          
