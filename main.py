import os
import random
import sys
import time
import requests
import asyncio
import concurrent.futures
import edge_tts
from groq import Groq
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
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

# Fail-safe dynamic model selector (strictly standard Llama/Mixtral models)
def get_working_model():
    try:
        models_page = groq_client.models.list()
        active_ids = [m.id for m in models_page.data]
        
        # Priority list of standard English text chat models
        preferred = [
            "llama-3.3-70b-versatile",
            "llama3-8b-8192",
            "llama3-70b-8192",
            "mixtral-8x7b-32768"
        ]
        
        for pref in preferred:
            if pref in active_ids:
                print(f"Using preferred model: {pref}")
                return pref
                
        # Strict filter: ONLY allow models starting with llama or mixtral, no slashes, no third-party APIs
        for m in active_ids:
            clean_id = m.lower()
            if (clean_id.startswith("llama") or clean_id.startswith("mixtral")) and "/" not in m and "guard" not in clean_id:
                print(f"Using filtered standard model: {m}")
                return m

    except Exception as e:
        print(f"Error fetching dynamic models: {e}")
        
    return "llama-3.3-70b-versatile"

# 1. Fast Script Generation
def generate_content():
    selected_model = get_working_model()
    
    system_prompt = "You are a direct horror scriptwriter. Do NOT include thinking process, intros, or explanations. Return ONLY requested output."
    user_prompt = """
    Generate a 30-second terrifying horror story for YouTube Shorts.
    Return response in this exact format:
    STORY: <The narrated horror story, around 50-60 words>
    PROMPT1: <Detailed horror image prompt for scene 1>
    PROMPT2: <Detailed horror image prompt for scene 2>
    PROMPT3: <Detailed horror image prompt for scene 3>
    """
    
    response = groq_client.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
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
            
    if not prompts:
        prompts = [
            "Terrifying dark corridor, cinematic horror lighting, photorealistic",
            "Creepy monster shadow in a dark room, hyperrealistic horror",
            "Scary spooky face emerging from darkness, 8k resolution"
        ]
        
    return story, prompts

# 2. Voiceover Generation
async def generate_audio(text, output_file="voiceover.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# 3. Parallel Image Downloading with Fallback Support
def download_single_image(args):
    prompt, filename = args
    encoded_prompt = requests.utils.quote(prompt)
    
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={random.randint(1, 999999)}"
    
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(filename, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded {filename} from Pollinations AI")
                return filename
        except Exception as e:
            print(f"Pollinations attempt {attempt + 1} failed for {filename}: {e}")
            time.sleep(2)
            
    # Reliable backup image if Pollinations is offline/timing out
    print(f"Fallback triggered for {filename}. Fetching backup image...")
    backup_url = f"https://picsum.photos/1080/1920?blur=2"
    try:
        response = requests.get(backup_url, timeout=30)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"Downloaded fallback image for {filename}")
            return filename
    except Exception as e:
        print(f"Fallback download failed: {e}")
        
    raise Exception(f"Failed to obtain image for {filename}")

def download_images_parallel(prompts):
    tasks = [(prompt, f"image_{i}.jpg") for i, prompt in enumerate(prompts)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(download_single_image, tasks))
    return results

# 4. Fast Video Rendering
def create_video(story, image_files, audio_file, output_file="final_short.mp4"):
    audio = AudioFileClip(audio_file)
    duration_per_image = audio.duration / len(image_files)
    
    clips = []
    for img_path in image_files:
        clip = ImageClip(img_path).set_duration(duration_per_image)
        clips.append(clip)
        
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video.write_videofile(
        output_file, 
        fps=30, 
        codec="libx264", 
        audio_codec="aac",
        preset="ultrafast",
        threads=4
    )

# 5. YouTube Uploading
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
    
    print("Generating images in parallel...")
    image_files = download_images_parallel(prompts)
        
    print("Creating video...")
    create_video(story, image_files, "voiceover.mp3")
    
    print("Uploading to YouTube...")
    title = f"Scary Story: {story[:40]}... #Shorts"
    upload_to_youtube("final_short.mp4", title, story + "\n\n#horror #shorts #scary")

if __name__ == "__main__":
    main()
    
