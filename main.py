import os
import random
import requests
import asyncio
from groq import Groq
import edge_tts
from moviepy.editor import (
    TextClip,
    AudioClip,
    ImageClip,
    CompositeVideoClip,
    CompositeAudioClip,
    AudioFileClip,
)

# ---------------------------------------------------------------------------
# 1. GENERATE HORROR STORY & VISUAL PROMPTS (GROQ)
# ---------------------------------------------------------------------------
def generate_story_and_prompts():
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    prompt = """
    Write a original, terrifying 30-second horror story suitable for YouTube Shorts.
    Return ONLY a JSON object with this exact structure:
    {
        "story": "The terrifying narrative text here...",
        "image_prompts": [
            "A creepy prompt for image 1",
            "A creepy prompt for image 2",
            "A creepy prompt for image 3"
        ]
    }
    """
    
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    import json
    data = json.loads(response.choices[0].message.content)
    return data["story"], data["image_prompts"]

# ---------------------------------------------------------------------------
# 2. GENERATE HIGH-QUALITY VOICE (EDGE-TTS)
# ---------------------------------------------------------------------------
async def generate_voiceover(text, output_file="voiceover.mp3"):
    # Deep, sinister voice for horror content
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(text, voice, rate="-5%", pitch="-10Hz")
    await communicate.save(output_file)

# ---------------------------------------------------------------------------
# 3. FETCH CINEMATIC HORROR IMAGES (POLLINATIONS AI)
# ---------------------------------------------------------------------------
def download_images(prompts):
    image_files = []
    for i, prompt in enumerate(prompts):
        enhanced_prompt = f"cinematic horror, highly detailed, photorealistic, dark atmosphere, 8k resolution, {prompt}"
        url = f"https://pollinations.ai/p/{requests.utils.quote(enhanced_prompt)}?width=1080&height=1920&seed={random.randint(1,10000)}&nologo=true"
        
        res = requests.get(url)
        filename = f"image_{i}.jpg"
        if res.status_code == 200:
            with open(filename, "wb") as f:
                f.write(res.content)
            image_files.append(filename)
        else:
            print(f"Failed to fetch image for prompt {i}")
    return image_files

# ---------------------------------------------------------------------------
# 4. RENDER HIGH-QUALITY VIDEO (MOVIEPY)
# ---------------------------------------------------------------------------
def assemble_video(story_text, image_files, voiceover_file, output_file="final_short.mp4"):
    audio_clip = AudioFileClip(voiceover_file)
    duration = audio_clip.duration
    
    # Calculate duration per image
    img_duration = duration / len(image_files) if image_files else duration
    
    clips = []
    for i, img_path in enumerate(image_files):
        clip = (
            ImageClip(img_path)
            .set_duration(img_duration)
            .set_start(i * img_duration)
            .resize(height=1920) # Ensures 9:16 vertical short layout
            .crop(x_center=540, y_center=960, width=1080, height=1920)
        )
        clips.append(clip)
    
    # Combine background images
    video = CompositeVideoClip(clips)
    
    # Add Captions/Subtitles
    txt_clip = (
        TextClip(
            story_text,
            fontsize=48,
            color='white',
            font='Arial-Bold',
            stroke_color='black',
            stroke_width=3,
            method='caption',
            size=(900, None)
        )
        .set_pos(('center', 'center'))
        .set_duration(duration)
    )
    
    final_video = CompositeVideoClip([video, txt_clip]).set_audio(audio_clip)
    final_video.write_videofile(
        output_file,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium"
    )

# ---------------------------------------------------------------------------
# MAIN PIPELINE EXECUTION
# ---------------------------------------------------------------------------
def main():
    print("Generating Horror Story & Prompts...")
    story, prompts = generate_story_and_prompts()
    
    print("Generating Voiceover...")
    asyncio.run(generate_voiceover(story))
    
    print("Downloading Visual Assets...")
    images = download_images(prompts)
    
    print("Rendering Final Video...")
    assemble_video(story, images, "voiceover.mp3", "final_short.mp4")
    print("DONE! Your video is ready at: final_short.mp4")

if __name__ == "__main__":
    main()
    
