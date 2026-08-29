import os
import json
import requests
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

# 1. GENERATE STORY SCRIPT WITH FALLBACK MODELS
def get_story_script():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    prompt = "Write a compelling 30-second suspense story script (approx 60 words). Return ONLY the script text."
    
    # List of models to attempt in order of priority
    candidate_models = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "qwen/qwen3-32b"
    ]
    
    last_response = None
    for model in candidate_models:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }
        res = requests.post(url, headers=headers, json=data).json()
        if 'choices' in res:
            print(f"Successfully generated script using model: {model}")
            return res['choices'][0]['message']['content']
        last_response = res
    
    raise Exception(f"All Groq models failed. Last Response: {last_response}")

# 2. GENERATE AUDIO
async def generate_voice(text, output_file="voice.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# 3. GENERATE VISUAL
def generate_image(prompt_text, output_file="background.jpg"):
    clean_prompt = requests.utils.quote(f"cinematic dark story illustration, {prompt_text}")
    url = f"https://gen.pollinations.ai/image/{clean_prompt}?width=1080&height=1920&nologo=true"
    
    img_data = requests.get(url).content
    with open(output_file, 'wb') as f:
        f.write(img_data)

# 4. EDIT VERTICAL VIDEO WITH ZOOM MOTION
def create_moving_video(audio_path, image_path, output_path="final_short.mp4"):
    audio = AudioFileClip(audio_path)
    
    image_clip = ImageClip(image_path).set_duration(audio.duration)
    moving_clip = image_clip.resize(lambda t: 1 + 0.03 * t)
    
    video = CompositeVideoClip([moving_clip.set_position("center")], size=(1080, 1920))
    video = video.set_audio(audio)
    
    video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

if __name__ == "__main__":
    print("Writing script...")
    script = get_story_script()
    
    print("Generating voiceover...")
    asyncio.run(generate_voice(script, "voice.mp3"))
    
    print("Generating cinematic art...")
    generate_image(script, "background.jpg")
    
    print("Rendering final video...")
    create_moving_video("voice.mp3", "background.jpg", "final_short.mp4")
    
    print("Video successfully generated!")
                  
