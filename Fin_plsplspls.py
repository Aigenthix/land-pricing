# !pip install pandas torch "doctr[torch]" opencv-python matplotlib

import cv2
import re
import numpy as np
import pandas as pd  # Import pandas
import torch  # Import torch for device detection
from typing import Tuple, Dict, Optional, List
import os

# Suppress DocTR font warnings
os.environ["DOCTR_SUPPRESS_WARNINGS"] = "1"
from doctr.models import ocr_predictor


class RobustLandRecordOCRDocTR:
    def __init__(self):
        # 3. Detect device and inform the user
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"PyTorch is using device: {device}")
        if str(device) == "cuda":
            print("CUDA (GPU) is available. DocTR will automatically use it.")
        else:
            print("CUDA not found. DocTR will run on CPU.")

        print("Loading DocTR model... (This may take a moment on first run)")
        # The predictor will automatically use the available GPU
        self.predictor = ocr_predictor(pretrained=True)
        print("DocTR model loaded.")

    def get_left_column_bbox(
        self, image: np.ndarray
    ) -> Tuple[int, int, int, int]:
        """Get a slimmer bounding box for the left column."""
        height, width = image.shape[:2]
        x = 0
        y = int(height * 0.20)
        w = int(width * 0.20)
        h = int(height * 0.35)
        return (x, y, w, h)

    def extract_text_doctr(self, image: np.ndarray) -> str:
        """Extract text from an image using DocTR."""
        result = self.predictor([image])
        return result.render()

    def extract_values(self, text: str) -> Dict[str, Optional[str]]:
        """
        Robustly extracts values as raw strings to preserve their original format
        (e.g., '6.25.00').
        """
        results = {"total_cultivable_area": None, "assessment": None}

        # --- Pattern for Total Cultivable Area ---
        area_pattern = r"Total\s*cultivable\s*Area?\s*(?P<value>[\d.]+)"
        area_match = re.search(area_pattern, text, re.IGNORECASE | re.DOTALL)

        if area_match:
            results["total_cultivable_area"] = area_match.group("value")

        # --- Pattern for Assessment ---
        assessment_pattern = r"^Assessment\s*$\s*(?P<value>[\d.]+)"
        assessment_match = re.search(
            assessment_pattern, text, re.IGNORECASE | re.MULTILINE
        )

        if assessment_match:
            results["assessment"] = assessment_match.group("value")

        return results

    def process_image(self, image_path: str) -> Dict:
        """
        Processes a single image to extract data without debugging output.
        """
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Could not load image: {image_path}")

        print(f"-> Processing {os.path.basename(image_path)}...")

        bbox = self.get_left_column_bbox(image)
        x, y, w, h = bbox
        left_column = image[y : y + h, x : x + w]

        raw_text = self.extract_text_doctr(left_column)
        results = self.extract_values(raw_text)

        return results


def main():
    ocr_processor = RobustLandRecordOCRDocTR()

    image_paths = [
        "images/1 (1).jpg",
        "images/1 (2).jpg",
        "images/1 (3).jpg",
        "images/1 (4).jpg",
        "images/1 (5).jpg",
    ]

    all_results: List[Dict] = []

    for path in image_paths:
        if not os.path.exists(path):
            print(f"Warning: Image file not found at '{path}'. Skipping.")
            continue
        try:
            # Process the image and get the dictionary of results
            output = ocr_processor.process_image(path)
            # Add the image name for use as a column header later
            output["image_name"] = os.path.basename(path)
            all_results.append(output)
        except Exception as e:
            print(f"An error occurred while processing {path}: {e}")

    # 1. & 2. Convert results to the desired DataFrame format
    if not all_results:
        print("\nNo images were processed successfully. Exiting.")
        return

    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(all_results)

    # Set the image name as the index
    df = df.set_index("image_name")

    # Transpose the DataFrame to get image names as columns
    df_transposed = df.T

    # Improve the index labels for clarity
    df_transposed = df_transposed.rename(
        index={
            "total_cultivable_area": "Total Cultivable Area",
            "assessment": "Assessment",
        }
    )

    print("\n\n--- OCR Extraction Results ---")
    print(df_transposed)

    # Optionally, save the DataFrame to a CSV file
    output_filename = "land_record_ocr_results.csv"
    df_transposed.to_csv(output_filename)
    print(f"\nResults have been saved to '{output_filename}'")


if __name__ == "__main__":
    main()