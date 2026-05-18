import os
import cv2
import torch
import numpy as np
from PIL import Image as PILImage
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
GDINO_MODEL_ID = 'IDEA-Research/grounding-dino-base'
SAM2_CONFIG = 'sam2_hiera_l.yaml'
SAM2_CKPT = '/home/ivan/checkpoints/sam2_hiera_large.pt'

INPUT_CAR_IMAGE = "image.png"
OUTPUT_MASK = "local_mask_rims.png"
OUTPUT_PREVIEW = "mask_preview.jpg"
DETECTION_PROMPT = "wheel rim."


def get_local_mask(image_path, prompt):
    print(f"[1/3] Loading models on {DEVICE}...")
    processor = AutoProcessor.from_pretrained(GDINO_MODEL_ID)
    gdino = AutoModelForZeroShotObjectDetection.from_pretrained(GDINO_MODEL_ID).to(DEVICE).eval()

    sam2_model = build_sam2(SAM2_CONFIG, SAM2_CKPT, device=DEVICE)
    predictor = SAM2ImagePredictor(sam2_model)

    image_cv = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
    pil_img = PILImage.fromarray(image_rgb)

    print(f"[2/3] Detecting objects with DINO: '{prompt}'")
    inputs = processor(images=pil_img, text=prompt, return_tensors='pt').to(DEVICE)
    with torch.no_grad():
        outputs = gdino(**inputs)

    results = processor.post_process_grounded_object_detection(
        outputs, inputs.input_ids,
        target_sizes=[pil_img.size[::-1]]
    )[0]

    # Filter by confidence threshold (box_threshold was removed in newer transformers)
    keep = results['scores'] >= 0.30
    results['boxes'] = results['boxes'][keep]
    results['scores'] = results['scores'][keep]
    results['labels'] = [lbl for lbl, k in zip(results['labels'], keep) if k]

    if len(results['boxes']) == 0:
        raise ValueError("No wheels detected! Try a different prompt.")

    print(f"[3/3] Segmenting with SAM 2 (found {len(results['boxes'])} wheels)...")
    predictor.set_image(image_rgb)

    h, w = image_cv.shape[:2]
    combined_mask = np.zeros((h, w), dtype=np.float32)

    for box in results['boxes']:
        x1, y1, x2, y2 = box.cpu().numpy()
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        bw, bh = x2 - x1, y2 - y1

        # Shrink box 15% per side → tight around rim disk, not tire
        s = 0.15
        rx1, ry1 = x1 + bw * s, y1 + bh * s
        rx2, ry2 = x2 - bw * s, y2 - bh * s

        # Positives: hub + 4 spoke points within shrunk rim area
        r = min(bw, bh) * 0.22
        input_points = np.array([
            [cx,      cy    ],   # hub
            [cx + r,  cy    ],   # right spoke
            [cx - r,  cy    ],   # left spoke
            [cx,      cy + r],   # bottom spoke
            [cx,      cy - r],   # top spoke
            # Negatives: original box edge midpoints — tire/fender zone
            [cx,      y1 + 4],
            [cx,      y2 - 4],
            [x1 + 4,  cy    ],
            [x2 - 4,  cy    ],
            [x1 + 4,  y1 + 4],
            [x2 - 4,  y2 - 4],
        ])
        input_labels = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0])

        with torch.inference_mode():
            masks, scores, _ = predictor.predict(
                point_coords=input_points,
                point_labels=input_labels,
                box=np.array([rx1, ry1, rx2, ry2])[None, :],
                multimask_output=True,
                return_logits=True
            )
        best = np.argmax(scores)
        soft_mask = 1.0 / (1.0 + np.exp(-masks[best].astype(np.float32)))
        np.maximum(combined_mask, soft_mask, out=combined_mask)

    mask_8bit = (combined_mask * 255).astype(np.uint8)
    cv2.imwrite(OUTPUT_MASK, mask_8bit)
    return image_cv, image_rgb, mask_8bit, results['boxes']


def visualize_mask(image_cv, image_rgb, mask_8bit, boxes):
    h, w = image_cv.shape[:2]

    # Red overlay on original image where mask is active
    overlay = image_cv.copy()
    red_channel = np.zeros_like(image_cv)
    red_channel[:, :, 2] = mask_8bit  # red in BGR
    alpha = (mask_8bit / 255.0)[:, :, None]
    overlay = (image_cv * (1 - alpha * 0.6) + red_channel * alpha * 0.6).astype(np.uint8)

    # Draw bounding boxes
    for box in boxes:
        x1, y1, x2, y2 = box.cpu().numpy().astype(int)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Grayscale mask panel
    mask_bgr = cv2.cvtColor(mask_8bit, cv2.COLOR_GRAY2BGR)

    # Stack: original | overlay | mask
    panel = np.concatenate([image_cv, overlay, mask_bgr], axis=1)

    # Labels
    label_h = 30
    label_bar = np.zeros((label_h, panel.shape[1], 3), dtype=np.uint8)
    for i, text in enumerate(["Original", "Mask Overlay", "Mask Only"]):
        x = i * w + 10
        cv2.putText(label_bar, text, (x, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    final = np.concatenate([label_bar, panel], axis=0)
    cv2.imwrite(OUTPUT_PREVIEW, final)
    print(f"\nPreview saved to: {OUTPUT_PREVIEW}")
    print(f"Mask saved to:    {OUTPUT_MASK}")

    # Show window if display is available
    try:
        cv2.imshow("Mask Preview (press any key to close)", final)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except Exception:
        print("(No display available — open the saved preview file)")


if __name__ == "__main__":
    try:
        image_cv, image_rgb, mask_8bit, boxes = get_local_mask(INPUT_CAR_IMAGE, DETECTION_PROMPT)
        print(f"\nMask generated successfully.")
        visualize_mask(image_cv, image_rgb, mask_8bit, boxes)
        print("\nDone. API call skipped — review the mask before proceeding.")
    except Exception as e:
        print(f"\nERROR: {e}")
