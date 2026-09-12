import os
import random
import sys
import time
import requests
import asyncio
import edge_tts
from groq import Groq
from moviepy.editor import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
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

# 1. Generate Horror Script & Image Prompts
def generate_content():
    prompt = """
    Generate a 30-second terrifying horror story for YouTube Shorts.
    Return the response in this exact format:
    STORY: <The full narrated horror story, around 50-60 words>
    PROMPT1: <Detailed image prompt for scene 1>
    PROMPT2: <Detailed image prompt for scene 2>
    PROMPT3: <Detailed image prompt for scene 3>
    """
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    content = response.choices[0].message.content
    
    story = ""
    prompts = []
    for line in content.split("\n"):
        if line.startswith("STORY:"):
            story = line.replace("STORY:", "").strip()
        elif line.startswith("PROMPT"):
            prompts.append(line.split(":", 1)[1].strip())
            
    return story, prompts

# 2. Generate Audio (Voiceover)
async def generate_audio(text, output_file="voiceover.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# 3. Download Image from Pollinations AI (Flux Model)
def download_image(prompt, filename):
    encoded_prompt = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={random.randint(1, 999999)}"
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
    else:
        raise Exception(f"Failed to fetch image: {response.status_code}")

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
    
    # Refresh token if needed
    creds.refresh(Request())
    
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["horror", "scary", "shorts", "scarystories", "creepy"],
            "categoryId": "24"  # Entertainment
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
