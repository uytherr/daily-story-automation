import PIL.Image
# Fix MoviePy compatibility with Pillow 10+
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import os
import random
import requests
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

# Diverse scary narrators for variation across daily runs
VOICES = [
    "en-US-ChristopherNeural",  # Deep male narrator
    "en-US-EricNeural",         # Dark intense male voice
    "en-GB-RyanNeural",         # Mysterious British male narrator
    "en-US-JennyNeural"         # Suspenseful female narrator
]

# Diverse dark art styles
ART_STYLES = [
    "uncanny dark horror illustration, cinematic lighting",
    "eerie gothic dark fantasy art, haunting nightmare concept",
    "found footage horror style, grainy atmospheric darkness",
    "creepy folklore horror art, dark shadows and surreal detail"
]

# 1. GENERATE COMPLETELY RANDOM HORROR STORY SCRIPT VIA GROQ
def get_story_script():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
        
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Fetch active models from Groq account dynamically
    models_url = "https://api.groq.com/openai/v1/models"
    models_res = requests.get(models_url, headers=headers).json()
    
    if "data" not in models_res:
        raise Exception(f"Failed to fetch model list from Groq. Response: {models_res}")
        
    available_models = [
        m["id"] for m in models_res["data"] 
        if "whisper" not in m["id"].lower() and "guard" not in m["id"].lower()
    ]
    
    if not available_models:
        raise Exception("No active text generation models found on your Groq account.")

    completions_url = "https://api.groq.com/openai/v1/chat/completions"
    
    prompt = (
        "Write a completely unique, terrifying horror legend or scary story in clear English. "
        "It can be about an ancient myth, a dark entity, a strange phenomenon, an urban legend, or an eerie encounter. "
        "Keep it atmospheric, chilling, and around 55-65 words (approx 30 seconds spoken). Return ONLY the script text."
    )
    
    last_response = None
    for model in available_models:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0  # High randomness ensures unique stories 3x a day
        }
        res = requests.post(completions_url, headers=headers, json=data).json()
        if 'choices' in res:
            print(f"Successfully generated script using model: {model}")
            return res['choices'][0]['message']['content']
        last_response = res

    raise Exception(f"Failed to generate script using discovered models. Last Response: {last_response}")

# 2. GENERATE SCARY VOICE OVER
async def generate_voice(text, output_file="voice.mp3"):
    selected_voice = random.choice(VOICES)
    print(f"Selected Narrator Voice: {selected_voice}")
    communicate = edge_tts.Communicate(text, selected_voice)
    await communicate.save(output_file)

# 3. GENERATE ATMOSPHERIC HORROR VISUAL
def generate_image(prompt_text, output_file="background.jpg"):
    selected_style = random.choice(ART_STYLES)
    short_prompt = prompt_text.replace("\n", " ")[:100]
    clean_prompt = requests.utils.quote(f"{selected_style}, {short_prompt}")
    
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1080&height=1920&nologo=true"
    
    res = requests.get(url, timeout=30)
    if res.status_code != 200 or not res.content:
        raise Exception(f"Image generation failed with HTTP status code: {res.status_code}")
        
    with open(output_file, 'wb') as f:
        f.write(res.content)

# 4. EDIT VERTICAL VIDEO WITH SLOW ZOOM
def create_moving_video(audio_path, image_path, output_path="final_short.mp4"):
    audio = AudioFileClip(audio_path)
    
    image_clip = ImageClip(image_path).set_duration(audio.duration)
    moving_clip = image_clip.resize(lambda t: 1 + 0.03 * t)
    
    video = CompositeVideoClip([moving_clip.set_position("center")], size=(1080, 1920))
    video = video.set_audio(audio)
    
    video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

if __name__ == "__main__":
    print("Writing horror script...")
    script = get_story_script()
    print(f"\nGenerated Horror Story:\n{script}\n")
    
    print("Generating voiceover...")
    asyncio.run(generate_voice(script, "voice.mp3"))
    
    print("Generating horror artwork...")
    generate_image(script, "background.jpg")
    
    print("Rendering vertical video...")
    create_moving_video("voice.mp3", "background.jpg", "final_short.mp4")
    
    print("Video successfully generated!")
    
