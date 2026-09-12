import os
import random
import sys
import time
import requests
import asyncio
import edge_tts
from groq import Groq
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Environment Variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

# Dynamically select an available and working text model from Groq
def get_working_model():
    try:
        models_page = groq_client.models.list()
        # Filter for text chat models (exclude whisper audio and guard models)
        available_models = [
            m.id for m in models_page.data 
            if "whisper" not in m.id and "guard" not in m.id
        ]
        
        # Priority order for text models
        preferred = [
            "llama-3.1-8b-instant", 
            "llama-3.3-70b-versatile", 
            "mixtral-8x7b-32768",
            "llama3-8b-8192"
        ]
        
        for pref in preferred:
            if pref in available_models:
                print(f"Using dynamic model: {pref}")
                return pref
                
        # Fallback to the first available text model
        if available_models:
            print(f"Using available model: {available_models[0]}")
            return available_models[0]
            
    except Exception as e:
        print(f"Failed to fetch dynamic models ({e}), using hardcoded fallback.")
        
    return "llama-3.1-8b-instant"

# 1. Generate Horror Script & Image Prompts
def generate_content():
    selected_model = get_working_model()
    
    prompt = """
    Generate a 30-second terrifying horror story for YouTube Shorts.
    Return the response in this exact format:
    STORY: <The full narrated horror story, around 50-60 words>
    PROMPT1: <Detailed image prompt for scene 1>
    PROMPT2: <Detailed image prompt for scene 2>
    PROMPT3: <Detailed image prompt for scene 3>
    """
    response = groq_client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    content = response.choices[0].message.content
    
    story = ""
    prompts = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("STORY:"):
            story = line.replace("STORY:", "").strip()
        elif line.startswith("PROMPT"):
            if ":" in line:
                prompts.append(line.split(":", 1)[1].strip())
            
    # Fallback prompt if list is empty
    if not prompts:
        prompts = [
            "Terrifying dark corridor, cinematic horror lighting, photorealistic",
            "Creepy monster shadow in a dark room, hyperrealistic horror",
            "Scary spooky face emerging from darkness, 8k resolution"
        ]
        
    return story, prompts

# 2. Generate Audio (Voiceover)
async def generate_audio(text, output_file="voiceover.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# 3. Download Image from Pollinations AI (Flux Model)
def download_image(prompt, filename):
    encoded_prompt = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={random.randint(1, 999999)}"
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
    else:
        raise Exception(f"Failed to fetch image: Status {response.status_code}")

# 4. Assemble Video with MoviePy
def create_video(story, image_files, audio_file, output_file="final_short.mp4"):
    audio = AudioFileClip(audio_file)
    duration_per_image = audio.duration / len(image_files)
    
    clips = []
    for img_path in image_files:
        clip = ImageClip(img_path).set_duration(duration_per_image)
        clips.append(clip)
        
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video.write_videofile(output_file, fps=30, codec="libx264", audio_codec="aac")

# 5. Authenticate and Upload to YouTube
def upload_to_youtube(video_path, title, description):
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["horror", "scary", "shorts", "scarystories", "creepy"],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")
            
    print(f"Video uploaded successfully! Video ID: {response.get('id')}")

# Pipeline Execution
def main():
    print("Generating story and prompts...")
    story, prompts = generate_content()
    
    print("Generating voiceover...")
    asyncio.run(generate_audio(story))
    
    image_files = []
    print("Generating images...")
    for i, prompt in enumerate(prompts):
        filename = f"image_{i}.jpg"
        download_image(prompt, filename)
        image_files.append(filename)
        
    print("Creating video...")
    create_video(story, image_files, "voiceover.mp3")
    
    print("Uploading to YouTube...")
    title = f"Scary Story: {story[:40]}... #Shorts"
    upload_to_youtube("final_short.mp4", title, story + "\n\n#horror #shorts #scary")

if __name__ == "__main__":
    main()
    
