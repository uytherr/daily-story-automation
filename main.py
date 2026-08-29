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

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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

# 2. GENERATE VOICE OVER
async def generate_voice(text, output_file="voice.mp3"):
    selected_voice = random.choice(VOICES)
    print(f"Selected Narrator Voice: {selected_voice}")
    communicate = edge_tts.Communicate(text, selected_voice)
    await communicate.save(output_file)

# 3. GENERATE 4 IMAGES WITH RETRIES & TIMEOUT FALLBACK
def generate_4_images(prompt_text):
    selected_style = random.choice(ART_STYLES)
    words = prompt_text.split()
    chunk_size = max(1, len(words) // 4)
    image_paths = []
    
    for i in range(4):
        segment_words = words[i * chunk_size : (i + 1) * chunk_size]
        segment_prompt = " ".join(segment_words)[:90].replace("\n", " ")
        clean_prompt = requests.utils.quote(f"{selected_style}, {segment_prompt}")
        
        filename = f"image_{i+1}.jpg"
        print(f"Downloading image {i+1}/4...")
        
        primary_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1080&height=1920&nologo=true"
        backup_url = f"https://loremflickr.com/1080/1920/horror,dark/all?lock={random.randint(1, 99999)}"
        
        success = False
        for attempt in range(3):
            try:
                res = requests.get(primary_url, timeout=60)
                if res.status_code == 200 and res.content:
                    with open(filename, 'wb') as f:
                        f.write(res.content)
                    image_paths.append(filename)
                    success = True
                    break
            except Exception:
                print(f"Attempt {attempt + 1} timed out for image {i+1}. Retrying...")
        
        if not success:
            print(f"Primary API failed. Fetching fallback image for {i+1}/4...")
            res = requests.get(backup_url, timeout=30)
            if res.status_code == 200 and res.content:
                with open(filename, 'wb') as f:
                    f.write(res.content)
                image_paths.append(filename)
            else:
                raise Exception(f"Failed to download image {i+1} from all sources.")
            
    return image_paths

# 4. CONCATENATE 4 IMAGES WITH MOTION ACROSS ENTIRE AUDIO
def create_moving_video(audio_path, image_paths, output_path="final_short.mp4"):
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    
    print(f"Audio Duration: {total_duration:.2f} seconds")
    clip_duration = total_duration / len(image_paths)
    
    video_clips = []
    for img_path in image_paths:
        img_clip = ImageClip(img_path).set_duration(clip_duration)
        moving_clip = img_clip.resize(lambda t: 1 + 0.03 * t)
        formatted_clip = CompositeVideoClip([moving_clip.set_position("center")], size=(1080, 1920)).set_duration(clip_duration)
        video_clips.append(formatted_clip)
    
    final_video = concatenate_videoclips(video_clips, method="compose")
    final_video = final_video.set_audio(audio)
    
    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )
    
    audio.close()

# 5. OPTIONAL DIRECT YOUTUBE UPLOADER
def upload_to_youtube(video_path):
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("YouTube credentials missing in GitHub Secrets. Saving video locally/artifacts.")
        return

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": "Terrifying Horror Legend You Haven't Heard #shorts #horror #scarystories",
            "description": "A terrifying daily scary story legend. Like and subscribe for more creepy stories!",
            "tags": ["shorts", "horror", "scarystories", "scary", "creepy", "urbanlegends"],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    print("Uploading video to YouTube Shorts...")
    response = request.execute()
    print(f"Video uploaded successfully! YouTube Video ID: {response.get('id')}")

if __name__ == "__main__":
    print("Step 1: Writing 40-60 second horror script...")
    script = get_story_script()
    print(f"\n--- Script ---\n{script}\n--------------\n")
    
    print("Step 2: Generating voiceover...")
    asyncio.run(generate_voice(script, "voice.mp3"))
    
    print("Step 3: Generating 4 scary images with timeout safeguards...")
    images = generate_4_images(script)
    
    print("Step 4: Rendering video with transitions...")
    create_moving_video("voice.mp3", images, "final_short.mp4")
    
    print("Step 5: Attempting YouTube upload...")
    upload_to_youtube("final_short.mp4")
    
    print("Workflow finished successfully!")
    
