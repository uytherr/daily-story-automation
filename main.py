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

# Environment Variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

# Dynamic model selection to prevent hardcoded model errors
def get_working_model():
    try:
        models_page = groq_client.models.list()
        
        # Filter out audio, vision, guardrails, and non-chat models
        valid_models = []
        for m in models_page.data:
            m_id = m.id.lower()
            if (
                "/" not in m.id 
                and "whisper" not in m_id 
                and "guard" not in m_id 
                and "vision" not in m_id
                and "orpheus" not in m_id
            ):
                valid_models.append(m.id)

        print(f"Available valid models for your API key: {valid_models}")

        if valid_models:
            selected = valid_models[0]
            print(f"Selected working model: {selected}")
            return selected

    except Exception as e:
        print(f"Error fetching dynamic models: {e}")
        
    raise RuntimeError("No available text chat models were found on your Groq API key.")

# 1. Viral Script Generation
def generate_content():
    selected_model = get_working_model()
    
    system_prompt = (
        "You are an expert horror YouTube Shorts writer. "
        "Do NOT include thinking processes, intros, or markdown. Return ONLY the exact structure requested."
    )
    
    user_prompt = """
    Create a 30-second horror short script designed for high retention and viral engagement on YouTube Shorts.
    
    CRITICAL STRUCTURE REQUIREMENTS:
    1. HOOK (0-3s): Start instantly in the middle of terrifying action. No pleasantries.
    2. TWIST (20-25s): End with a sudden, disturbing twist or cliffhanger that forces viewers to rewatch.
    3. VISUALS: Highly descriptive, vivid, atmospheric imagery prompts optimized for AI art generators.
    
    Return response in this exact format:
    STORY: <The narrated horror story, strictly 50 to 60 words>
    PROMPT1: <Detailed cinematic horror image prompt for scene 1>
    PROMPT2: <Detailed cinematic horror image prompt for scene 2>
    PROMPT3: <Detailed cinematic horror image prompt for scene 3>
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
            "Terrifying dark corridor, cinematic horror lighting, photorealistic, 8k resolution",
            "Creepy monster shadow looming in a dark room, hyperrealistic horror",
            "Scary uncanny face emerging from the dark wall, eerie atmosphere"
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
            
    # Backup trigger if Pollinations times out
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
    
    print("\n--------------------------------------------------")
    print("SUCCESS! Video generation complete.")
    print("Your video is saved at: final_short.mp4")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
    
