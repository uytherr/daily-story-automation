import PIL.Image
# Fix MoviePy compatibility with Pillow 10+
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import os
import random
import requests
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips

VOICES = [
    "en-US-ChristopherNeural",  # Deep male narrator
    "en-US-EricNeural",         # Dark intense male voice
    "en-GB-RyanNeural",         # Mysterious British male narrator
    "en-US-JennyNeural"         # Suspenseful female narrator
]

ART_STYLES = [
    "uncanny dark horror illustration, cinematic lighting, ultra detailed",
    "eerie gothic dark fantasy art, haunting nightmare concept",
    "found footage horror style, grainy atmospheric darkness, scary perspective",
    "creepy folklore horror art, dark shadows and surreal terrifying detail"
]

# 1. GENERATE LONGER SCRIPT (40-60 SECONDS WITH INTRO & OUTRO)
def get_story_script():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
        
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
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
        "Write a terrifying horror legend or scary story in clear English.\n\n"
        "STRICT STRUCTURE REQUIRED:\n"
        "1. Start EXACTLY with: 'Welcome back horror lovers. Today we have a story that will chill you to the bone.'\n"
        "2. Tell a captivating, eerie horror story about an ancient legend, cryptid, or spooky phenomenon (around 120 words).\n"
        "3. End the story EXACTLY with these two sentences:\n"
        "'Remember, it might catch you if you don't look over your shoulder right now. Don't forget to like and subscribe for more terrifying legends.'"
    )
    
    last_response = None
    for model in available_models:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.95
        }
        res = requests.post(completions_url, headers=headers, json=data).json()
        if 'choices' in res:
            print(f"Successfully generated script using model: {model}")
            return res['choices'][0]['message']['content']
        last_response = res

    raise Exception(f"Failed to generate script. Last Response: {last_response}")

# 2. GENERATE VOICE OVER AND SAVE FILE
async def generate_voice(text, output_file="voice.mp3"):
    selected_voice = random.choice(VOICES)
    print(f"Selected Narrator Voice: {selected_voice}")
    communicate = edge_tts.Communicate(text, selected_voice)
    await communicate.save(output_file)

# 3. GENERATE 4 DISTINCT IMAGES FOR VISUAL VARIETY
def generate_4_images(prompt_text):
    selected_style = random.choice(ART_STYLES)
    words = prompt_text.split()
    
    # Divide the script into 4 segments so each image represents a different part of the story
    chunk_size = max(1, len(words) // 4)
    image_paths = []
    
    for i in range(4):
        segment_words = words[i * chunk_size : (i + 1) * chunk_size]
        segment_prompt = " ".join(segment_words)[:90].replace("\n", " ")
        clean_prompt = requests.utils.quote(f"{selected_style}, {segment_prompt}")
        
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1080&height=1920&nologo=true"
        filename = f"image_{i+1}.jpg"
        
        print(f"Downloading image {i+1}/4...")
        res = requests.get(url, timeout=30)
        
        if res.status_code == 200 and res.content:
            with open(filename, 'wb') as f:
                f.write(res.content)
            image_paths.append(filename)
        else:
            raise Exception(f"Failed to download image {i+1}")
            
    return image_paths

# 4. CONCATENATE 4 IMAGES WITH MOTION ACROSS THE ENTIRE AUDIO
def create_moving_video(audio_path, image_paths, output_path="final_short.mp4"):
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    
    print(f"Audio Duration: {total_duration:.2f} seconds")
    
    # Calculate screen time per image (e.g., 50s / 4 images = 12.5s per image)
    clip_duration = total_duration / len(image_paths)
    
    video_clips = []
    for i, img_path in enumerate(image_paths):
        # Create image clip for its allocated duration
        img_clip = ImageClip(img_path).set_duration(clip_duration)
        
        # Apply slight zoom effect
        moving_clip = img_clip.resize(lambda t: 1 + 0.03 * t)
        
        # Crop/Format to 1080x1920
        formatted_clip = CompositeVideoClip([moving_clip.set_position("center")], size=(1080, 1920)).set_duration(clip_duration)
        video_clips.append(formatted_clip)
    
    # Combine all 4 image clips sequentially
    final_video = concatenate_videoclips(video_clips, method="compose")
    final_video = final_video.set_audio(audio)
    
    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )
    
    # Close audio handle
    audio.close()

if __name__ == "__main__":
    print("Step 1: Writing 40-60 second horror script...")
    script = get_story_script()
    print(f"\n--- Script ---\n{script}\n--------------\n")
    
    print("Step 2: Generating voiceover...")
    asyncio.run(generate_voice(script, "voice.mp3"))
    
    print("Step 3: Generating 4 scary images...")
    images = generate_4_images(script)
    
    print("Step 4: Rendering video with 4 image transitions...")
    create_moving_video("voice.mp3", images, "final_short.mp4")
    
    print("Success! 4-image 40-60 second video generated successfully!")
            
