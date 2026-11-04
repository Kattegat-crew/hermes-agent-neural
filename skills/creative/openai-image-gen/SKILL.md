---
name: openai-image-gen
description: "Use when generating images with DALL-E 3 / OpenAI."
tags: [imagenes, dalle-3, openai, generacion, assets, marketing, image-generation, creative]
license: MIT
compatibility: hermes, opencode, python, bash
metadata:
  hermes:
    tags: [image-generation, dalle-3, openai, art, creative, assets]
    category: creative
---

# OpenAI Image Generation Best Practices (DALL-E 3)

Operational guide for automating image generation, prompt tuning, and asset downloading via OpenAI's Image API and compatible proxies.

## 1. Supported Parameters & Standards

| Parameter | Options / Recommendations | Description |
|-----------|---------------------------|-------------|
| `model` | `dall-e-3` | Standard production model. |
| `size` | `1024x1024` (Square), `1024x1792` (9:16 Vertical Reel/Story), `1792x1024` (16:9 Landscape) | Aspect ratio selection. |
| `quality` | `standard` (fast/cheaper) or `hd` (maximum fine detail) | Use `hd` for final marketing assets. |
| `response_format` | `b64_json` (preferred for headless) or `url` | `url` expires after 60 minutes; use `b64_json` for direct saving. |

---

## 2. Headless Python Generation Script

```python
import os, json, base64
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_asset(prompt: str, output_path: str, size: str = "1024x1024", quality: str = "standard"):
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality=quality,
        response_format="b64_json",
        n=1
    )
    
    image_data = response.data[0]
    revised_prompt = image_data.revised_prompt
    raw_b64 = image_data.b64_json
    
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(raw_b64))
        
    print(f"✅ Image saved to {output_path}")
    print(f"📝 Revised prompt: {revised_prompt}")

if __name__ == "__main__":
    generate_asset(
        prompt="Professional high-tech server rack in a dark cybernetic data center with glowing teal and purple fiber-optic cables, 8k, cinematic lighting",
        output_path="/tmp/datacenter.png",
        size="1792x1024",
        quality="hd"
    )
```

---

## 3. Prompt Engineering Guidelines for DALL-E 3

1. **Be Concrete, Not Keyword-Stuffed**: DALL-E 3 responds poorly to comma-separated buzzwords ("photorealistic, octane render, 8k"). Instead, write descriptive natural sentences detailing the subject, lighting, style, lens, and atmosphere.
2. **Text Rendering**: Wrap exact desired text in quotes (e.g. `a billboard that says "NEURAL CREW"`). Keep in-image text short (1-3 words) to minimize typographic hallucinations.
3. **Inspect `revised_prompt`**: OpenAI rewrites input prompts for safety and detail. Always log `revised_prompt` to understand the final generation context.
