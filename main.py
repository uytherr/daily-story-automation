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

# ---------------------------------------------------------------------------
# Environment Variables & Client Setup
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is not set. Add it to GitHub Secrets.")

groq_client = Groq(api_key=GROQ_API_KEY)

# ---------------------------------------------------------------------------
# Dynamic Model Selection
# ---------------------------------------------------------------------------
def get_working_model():
    try:
        models_page = groq_client.models.list()
        
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
        
    print("Defaulting to llama-3.3-70b-versatile fallback model.")
    return "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# 1. Complete Horror Story Script Generation
# ---------------------------------------------------------------------------
def generate_content():
    selected_model = get_working_model()
    
    system_prompt = (
        "You are an expert horror narrative writer for YouTube Shorts. "
        "Do NOT include thinking processes, explanations, or markdown syntax like **. "
        "Return ONLY the requested labels."
    )
    
    user_prompt = """
    Write a complete, self-contained terrifying horror story that happens entirely at a train station late at night.
    
    CRITICAL REQUIREMENTS FOR THE STORY:
    1. INTRO: MUST start EXACTLY with: "Welcome back horror lovers. Today we will count down five unnerving reasons you should never stay late at an abandoned train station..." followed by a creepy reason.
    2. NARRATIVE: Tell a full, scary, complete narrative at the station. Do not leave a cliffhanger; complete the event.
    3. OUTRO: MUST end EXACTLY with a unique variation of this warning: "...because if you don't look behind you, it might happen with you."
    4. LENGTH: The narration text MUST be between 120 and 170 words long to guarantee the video lasts at least 40 to 60 seconds.
    
    Return response in this EXACT format:
    STORY: <Full narrated horror story matching all intro, station setting, plot completion, and outro rules>
    PROMPT1: <Detailed cinematic dark horror image prompt of the train station platform>
    PROMPT2: <Detailed cinematic dark horror image prompt of a scary phantom train or entity on tracks>
    PROMPT3: <Detailed cinematic dark horror image prompt of the terrifying conclusion at the station>
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
            
    if not story:
        story = (
            "Welcome back horror lovers. Today we will count down five unnerving reasons you should never stay late at an abandoned train station. "
            "At 2 AM, Mark sat alone on the cold platform bench waiting for a train that hadn't run in thirty years. "
            "Suddenly, a heavy screech of rusted wheels echoed through the fog. A pitch-black train pulled up, its windows filled with pale, motionless faces staring right at him. "
            "The rusted doors opened with a wet thud. As Mark stepped back to run, an icy hand grabbed his throat from behind and pulled him into the dark. "
            "Police found only his phone the next morning. Be careful waiting alone at night, because if you don't look behind you, it might happen with you."
        )

    if len(prompts) < 3:
        prompts = [
            "Abandoned eerie train station platform at night, thick fog, cinematic horror lighting, 8k resolution, vertical 9:16",
            "Ghostly black train arriving on rusted tracks, pale faces in dark windows, terrifying atmosphere, hyperrealistic horror",
            "Creepy shadow hand reaching from the dark on an empty train platform, eerie horror scene"
        ]
        
    return story, prompts

# ---------------------------------------------------------------------------
# 2. Voiceover Generation (edge-tts)
# ---------------------------------------------------------------------------
async def generate_audio(text, output_file="voiceover.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# ---------------------------------------------------------------------------
# 3. Parallel Image Downloading with Fallbacks
# ---------------------------------------------------------------------------
def download_single_image(args):
    prompt, filename = args
    encoded_prompt = requests.utils.quote(prompt)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={random.randint(1, 999999)}"
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(filename, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded {filename} from Pollinations AI")
                return filename
        except Exception as e:
            print(f"Pollinations attempt {attempt + 1} failed for {filename}: {e}")
            time.sleep(2)
            
    print(f"Fallback triggered for {filename}. Fetching backup image...")
    backup_url = "https://picsum.photos/1080/1920?blur=2"
    try:
        response = requests.get(backup_url, headers=headers, timeout=30)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"Downloaded fallback image for {filename}")
            return filename
    except Exception as e:
        print(f"Fallback download failed: {e}")
        
    raise RuntimeError(f"Failed to obtain image for {filename}")

def download_images_parallel(prompts):
    tasks = [(prompt, f"image_{i}.jpg") for i, prompt in enumerate(prompts)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(download_single_image, tasks))
    return results

# ---------------------------------------------------------------------------
# 4. Video Assembly
# ---------------------------------------------------------------------------
def create_video(story, image_files, audio_file, output_file="final_short.mp4"):
    audio = AudioFileClip(audio_file)
    print(f"Total audio duration: {audio.duration:.2f} seconds")
    
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
    
    video.close()
    audio.close()
    for clip in clips:
        clip.close()

# ---------------------------------------------------------------------------
# Pipeline Execution
# ---------------------------------------------------------------------------
def main():
    print("Generating complete station horror script...")
    story, prompts = generate_content()
    print(f"\n--- Generated Story ---\n{story}\n----------------------\n")
    
    print("Generating voiceover...")
    asyncio.run(generate_audio(story))
    
    print("Generating images in parallel...")
    image_files = download_images_parallel(prompts)
        
    print("Creating final video...")
    create_video(story, image_files, "voiceover.mp3")
    
    print("\n--------------------------------------------------")
    print("SUCCESS! Full station horror video generated.")
    print("Output path: final_short.mp4")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
    
