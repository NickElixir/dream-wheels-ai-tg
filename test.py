


import os
import cv2
import torch
import numpy as np
import io
import fal_client
from PIL import Image as PILImage
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
import webbrowser
import urllib.request as _req
os.environ["FAL_KEY"] = "4184f4b3-6155-45ef-8e4d-00dbfb2aed28:490409eb31da56a95cfea4fd967d9465"



# ─────────────────────────────────────────────────────────────────────────────
# CONFIG & CREDENTIALS
# ─────────────────────────────────────────────────────────────────────────────

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
GDINO_MODEL_ID = "IDEA-Research/grounding-dino-tiny" # Tiny быстрее и часто точнее для колес
SAM2_CONFIG = "sam2_hiera_l.yaml"
SAM2_CKPT = "/home/ivan/checkpoints/sam2_hiera_large.pt" 

INPUT_CAR_IMAGE = "car.png"
REFERENCE_RIMS_IMAGE = "rim.png"
OUTPUT_MASK = "local_mask_rims.png"
DETECTION_PROMPT = "wheel."

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: LOCAL PERCEPTION (DINO + SAM 2)
# ─────────────────────────────────────────────────────────────────────────────

def get_local_mask(image_path, prompt="wheel.", output_path="final_mask.png"):
    print(f"[1/3] Loading models on {DEVICE}...")
    processor = AutoProcessor.from_pretrained(GDINO_MODEL_ID)
    gdino = AutoModelForZeroShotObjectDetection.from_pretrained(GDINO_MODEL_ID).to(DEVICE).eval()
    
    sam2_model = build_sam2(SAM2_CONFIG, SAM2_CKPT, device=DEVICE)
    predictor = SAM2ImagePredictor(sam2_model)

    image_cv = cv2.imread(image_path)
    if image_cv is None:
        raise FileNotFoundError(f"Не удалось загрузить {image_path}")
    
    image_rgb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
    pil_img = PILImage.fromarray(image_rgb)
    h, w = image_cv.shape[:2]
    
    print(f"[2/3] Detecting objects with DINO: '{prompt}'")
    inputs = processor(images=pil_img, text=prompt, return_tensors='pt').to(DEVICE)
    with torch.no_grad():
        outputs = gdino(**inputs)
    
    results = processor.post_process_grounded_object_detection(
        outputs, inputs.input_ids,
        target_sizes=[pil_img.size[::-1]]
    )[0]

    img_area = w * h
    visible_indices = []
    for i, (box, score) in enumerate(zip(results['boxes'], results['scores'])):
        if score < 0.30: continue
        x1, y1, x2, y2 = box.cpu().numpy()
        bw, bh = x2 - x1, y2 - y1
        aspect = min(bw, bh) / max(bw, bh)
        # Твоя логика фильтрации: квадратность и площадь
        if aspect > 0.5 and (bw * bh) > img_area * 0.015:
            visible_indices.append(i)

    if not visible_indices:
        raise ValueError("Колеса не найдены! Попробуй изменить DETECTION_PROMPT.")

    print(f"[3/3] Segmenting with SAM 2 (found {len(visible_indices)} wheels)...")
    predictor.set_image(image_rgb)
    final_mask = np.zeros((h, w), dtype=np.uint8)

    for idx in visible_indices:
        box = results['boxes'][idx].cpu().numpy()
        with torch.inference_mode():
            masks, scores, _ = predictor.predict(
                box=box[None, :],
                multimask_output=False 
            )
        
        mask_binary = (masks[0] > 0.0).astype(np.uint8) * 255
        
        # Морфология: сжимаем на 15 пикселей, чтобы не задеть резину
        kernel = np.ones((15, 15), np.uint8)
        eroded_mask = cv2.erode(mask_binary, kernel, iterations=1)
        final_mask = cv2.bitwise_or(final_mask, eroded_mask)

    cv2.imwrite(output_path, final_mask)
    return output_path


def cloud_rim_replacement(car_path, mask_path, ref_path):
    print("\n--- Flux Kontext Max: rim replacement with reference ---")

    try:
        car_url = fal_client.upload_file(car_path)
        mask_url = fal_client.upload_file(mask_path)
        ref_url = fal_client.upload_file(ref_path)

        print("Processing with Kontext...")
        handler = fal_client.submit(
            "fal-ai/flux-pro/kontext/max",
            arguments={
                "image_url": car_url,
                "mask_url": mask_url,
                "prompt": (
                    f"Replace the car wheel rims with the design from this reference: {ref_url}. "
                    "New rims: matte black, 5 wide spokes, flat black finish, no chrome. "
                    "Keep tires, car body, color, and background unchanged. "
                    "Match perspective and lighting of each wheel. Photorealistic, 8k."
                ),
                "guidance_scale": 7.5,
            }
        )

        result = handler.get()

        if result and "images" in result and len(result["images"]) > 0:
            return result["images"][0]["url"]
        return None

    except Exception as e:
        print(f"API Error: {str(e)}")
        return None
    
import fal_client


def cloud_rim_replacement_nano_no_mask(car_path, ref_path):
    print("\n--- Sending to Nano Banana 2: Image-to-Image (No Mask) ---")
    try:
        # Upload both images — order matters: base first, reference second
        car_url = fal_client.upload_file(car_path)
        ref_url = fal_client.upload_file(ref_path)

        result = fal_client.subscribe(
            "fal-ai/nano-banana-2/edit",
            arguments={
                # Base image first, reference image(s) after
                "image_urls": [car_url, ref_url],

                "prompt": (
                    "Professional automotive photography. In the first image, "
                    "replace the car's wheel rims with the exact rims shown in "
                    "the second image — match their shape, color, material, and "
                    "spoke design precisely. Keep the car's body, paint color, "
                    "pose, lighting, and background completely unchanged. "
                    "Photorealistic, sharp detail, accurate reflections."
                ),

                # Real, supported parameters:
                "num_images": 1,
                "aspect_ratio": "auto",
                "resolution": "1K",          # bump to 2K for detail on rims
                "output_format": "png",
                "safety_tolerance": "6",     # least strict; can't fully disable
                "thinking_level": "high",    # helps with precise edits (+$0.002)
            },
            with_logs=True,
            on_queue_update=lambda u: (
                [print(l["message"]) for l in u.logs]
                if isinstance(u, fal_client.InProgress) else None
            ),
        )

        if result and "images" in result and result["images"]:
            return result["images"][0]["url"]
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None


def cloud_rim_replacement_kontext_inpaint(car_path, ref_path, mask_path):
    print("\n--- Sending to FLUX.1 Kontext LoRA Inpaint (Base + Reference + Mask) ---")
    try:
        # Upload all three
        car_url = fal_client.upload_file(car_path)
        ref_url = fal_client.upload_file(ref_path)
        mask_url = fal_client.upload_file(mask_path)

        result = fal_client.subscribe(
            "fal-ai/flux-kontext-lora/inpaint",
            arguments={
                "image_url": car_url,            # base: the car
                "reference_image_url": ref_url,  # reference: the rims to copy
                "mask_url": mask_url,            # mask: white = edit area (wheels)
                "prompt": (
                    "wheel rims matching the reference image in design and color, "
                    "with reflections and highlights naturally adapted to the car's lighting environment. "
                    "Correct perspective for each wheel. Tires and bodywork unchanged. "
                    "Photorealistic, sharp focus, professional automotive photography."
                ),
                # Real, supported parameters for this endpoint:
                "num_inference_steps":30,
                "guidance_scale": 4.5,
                "strength": 0.9,           # higher = more change in the masked area
                "num_images": 1,
                "output_format": "png",
                "acceleration": "none",     # "regular" or "high" for faster (lower quality)
                "enable_safety_checker": True,
                # Optional: pass any custom LoRAs you've trained
                # "loras": [{"path": "https://.../my-rim-lora.safetensors", "scale": 1.0}],
            },
            with_logs=True,
            on_queue_update=lambda u: (
                [print(l["message"]) for l in u.logs]
                if isinstance(u, fal_client.InProgress) else None
            ),
        )
        if result and "images" in result and result["images"]:
            return result["images"][0]["url"]
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None
# ─────────────────────────────────────────────────────────────────────────────
# RUN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        # 1. Локальная маска
        local_mask = get_local_mask(INPUT_CAR_IMAGE, DETECTION_PROMPT, OUTPUT_MASK)
        print(f"Local mask ready: {local_mask}")

        # 2. Облачная генерация
        final_result_url = cloud_rim_replacement_kontext_inpaint(
                car_path=INPUT_CAR_IMAGE,
                ref_path=REFERENCE_RIMS_IMAGE,
                mask_path=local_mask,
)
        # final_result_url = cloud_rim_replacement_nano_no_mask(INPUT_CAR_IMAGE, REFERENCE_RIMS_IMAGE)
        
        if final_result_url:
            print(f"\nSuccess! Result: {final_result_url}")

            # Сохранение результата
            raw = _req.urlopen(final_result_url).read()
            img = PILImage.open(io.BytesIO(raw)).convert("RGBA")
            img.save("result.png", "PNG")
            print("Saved as result.png")

            webbrowser.open(final_result_url)
        else:
            print("Failed to get result from API.")

    except Exception as e:
        print(f"\nError in pipeline: {e}")# ─────────────────────────────────────────────────────────────────────────────
