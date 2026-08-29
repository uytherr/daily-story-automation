import os
import json
import requests
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

# 1. GENERATE STORY SCRIPT BY AUTOMATICALLY DISCOVERING ACTIVE MODELS
def get_story_script():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
        
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Fetch active models
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

    print(f"Discovered available models: {available_models}")
    
    completions_url = "https://api.groq.com/openai/v1/chat/completions"
    prompt = "Write a compelling 30-second suspense story script (approx 60 words). Return ONLY the script text."
    
    last_response = None
    for model in available_models:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }
        res = requests.post(completions_url, headers=headers, json=data).json()
        if 'choices' in res:
            print(f"Successfully generated script using model: {model}")
            return res['choices'][0]['message']['content']
        last_response = res

    raise Exception(f"Failed to generate script using discovered models. Last Response: {last_response}")

# 2. GENERATE AUDIO
async def generate_voice(text, output_file="voice.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# 3. GENERATE VISUAL (SAFE DOWNLOAD WITH PROMPT TRUNCATION)
def generate_image(prompt_text, output_file="background.jpg"):
    # Extract short prompt summary (first 100 chars) to prevent HTTP 400 errors
    short_prompt = prompt_text.replace("\n", " ")[:100]
    clean_prompt = requests.utils.quote(f"cinematic dark suspense illustration, {short_prompt}")
    
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1080&height=1920&nologo=true"
    
    res = requests.get(url, timeout=30)
    if res.status_code != 200 or not res.content:
        raise Exception(f"Image generation failed with HTTP status code: {res.status_code}")
        
    with open(output_file, 'wb') as f:
        f.write(res.content)

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
                                                                          
