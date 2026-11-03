import streamlit as st
import os
import tempfile
import asyncio
import edge_tts
from deep_translator import GoogleTranslator
import whisper
from moviepy.editor import VideoFileClip, AudioFileClip

st.set_page_config(page_title="THUTA — Burmese Drama & Dubbing Studio", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: bold; color: #FF4B4B; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1rem; color: #888; margin-bottom: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🎬 THUTA — Burmese Drama & Auto-Dubbing Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ဗီဒီယို Upload တင်ပြီး မြန်မာဘာသာပြန်နှင့် AI နောက်ခံစကားပြော အလိုအလျောက် ထုတ်လုပ်သည့်စနစ်</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Settings (ပြင်ဆင်ချက်များ)")
    voice_choice = st.selectbox(
        "🎙️ မြန်မာ AI အသံ ရွေးချယ်ရန်",
        options=[
            ("သီဟ (အမျိုးသားအသံ)", "my-MM-ThihaNeural"),
            ("နီလာ (အမျိုးသမီးအသံ)", "my-MM-NilarNeural")
        ],
        format_func=lambda x: x[0]
    )
    selected_voice = voice_choice[1]
    speech_rate = st.slider("⚡ စကားပြောနှုန်း (Speed)", min_value=-30, max_value=50, value=5, step=5, format="%d%%")
    model_size = st.selectbox("🧠 Whisper Model အရွယ်အစား", ["tiny", "base", "small"], index=1)

@st.cache_resource
def load_whisper_model(size):
    return whisper.load_model(size)

async def generate_burmese_tts(text, voice, rate, output_path):
    rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_path)

tab1, tab2 = st.tabs(["📤 Video Auto-Dubbing (ဗီဒီယို အသံသွင်းရန်)", "📝 Script to Voice (စာသားမှ အသံထုတ်ရန်)"])

with tab1:
    uploaded_video = st.file_uploader("ဗီဒီယိုဖိုင် ရွေးချယ်ပါ (MP4, MOV, MKV)", type=["mp4", "mov", "mkv"])
    
    if uploaded_video is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("မူရင်း ဗီဒီယို")
            st.video(uploaded_video)
            
        if st.button("🚀 စတင် ဘာသာပြန်ပြီး အသံသွင်းမည် (Start Processing)", type="primary", use_container_width=True):
            with st.spinner("အဆင့် ၁/၄ - ဗီဒီယိုဖိုင်ကို စစ်ဆေးနေပါသည်..."):
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded_video.read())
                video_path = tfile.name

            try:
                with st.spinner("အဆင့် ၂/၄ - မူရင်းအသံကို စာသားအဖြစ် ပြောင်းနေပါသည် (Whisper)..."):
                    model = load_whisper_model(model_size)
                    result = model.transcribe(video_path)
                    original_text = result["text"].strip()
                    st.info(f"**မူရင်းစာသား:** {original_text}")

                with st.spinner("အဆင့် ၃/၄ - မြန်မာဘာသာသို့ ပြန်ဆိုနေပါသည်..."):
                    translated_text = GoogleTranslator(source='auto', target='my').translate(original_text)
                    st.success(f"**မြန်မာဘာသာပြန်:** {translated_text}")

                with st.spinner("အဆင့် ၄/၄ - မြန်မာ AI အသံသွင်းပြီး ဗီဒီယိုနှင့် ပေါင်းစပ်နေပါသည်..."):
                    tts_path = os.path.join(tempfile.gettempdir(), "burmese_dub.mp3")
                    asyncio.run(generate_burmese_tts(translated_text, selected_voice, speech_rate, tts_path))
                    
                    output_video_path = os.path.join(tempfile.gettempdir(), "thuta_dubbed_output.mp4")
                    video_clip = VideoFileClip(video_path)
                    audio_clip = AudioFileClip(tts_path)
                    
                    final_clip = video_clip.set_audio(audio_clip)
                    final_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac", logger=None)
                    
                    video_clip.close()
                    audio_clip.close()

                with col2:
                    st.subheader("✅ မြန်မာနောက်ခံစကားပြော ဗီဒီယို")
                    st.video(output_video_path)
                    with open(output_video_path, "rb") as f:
                        st.download_button(
                            label="⬇️ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲရန် (Download MP4)",
                            data=f,
                            file_name="thuta_drama_dubbed.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
            except Exception as e:
                st.error(f"Error ဖြစ်ပေါ်နေပါသည်: {str(e)}")

with tab2:
    st.subheader("မြန်မာစာသားမှ AI အသံဖိုင် တိုက်ရိုက်ထုတ်ရန်")
    custom_script = st.text_area("မြန်မာစာသား ရိုက်ထည့်ပါ...", height=150)
    if st.button("🎙️ အသံဖိုင်ထုတ်မည်", use_container_width=True):
        if custom_script.strip():
            tts_only_path = os.path.join(tempfile.gettempdir(), "thuta_voice.mp3")
            asyncio.run(generate_burmese_tts(custom_script, selected_voice, speech_rate, tts_only_path))
            st.audio(tts_only_path)
            with open(tts_only_path, "rb") as f:
                st.download_button("⬇️ MP3 ဒေါင်းလုဒ်ဆွဲရန်", data=f, file_name="thuta_voiceover.mp3", mime="audio/mp3")
